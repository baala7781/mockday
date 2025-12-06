/**
 * Hook for recording audio from microphone and streaming raw PCM16 to WebSocket
 * Uses AudioContext + AudioWorklet to capture raw PCM16 for Deepgram Live API
 * AudioWorklet runs on audio thread (not main thread), preventing CPU backpressure freezes
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export interface UseAudioRecorderOptions {
  onAudioChunk?: (chunk: string, sampleRate: number, channels: number) => void;
  onSilenceDetected?: () => void; // Called when silence threshold is reached
  chunkInterval?: number; // ms between chunks (not used for PCM16, but kept for compatibility)
  sampleRate?: number;
  channels?: number;
  mimeType?: string; // Deprecated - always uses PCM16 now
  silenceThreshold?: number; // Audio level below which is considered silence (0-100)
  silenceDuration?: number; // Duration of silence in ms before triggering (default: 3000ms)
}

export interface UseAudioRecorderReturn {
  startRecording: () => Promise<void>;
  stopRecording: (force?: boolean) => boolean; // Returns true if actually stopped, false if race condition prevented stop. force=true bypasses race condition check.
  pauseRecording: () => void;
  resumeRecording: () => void;
  isRecording: boolean;
  isPaused: boolean;
  hasPermission: boolean;
  error: string | null;
  audioLevel: number; // 0-100
}

export function useAudioRecorder(options: UseAudioRecorderOptions = {}): UseAudioRecorderReturn {
  const {
    onAudioChunk,
    onSilenceDetected,
    chunkInterval = 100, // 100ms chunks for low latency
    sampleRate = 16000,
    channels = 1,
    mimeType = 'audio/webm;codecs=opus', // WebM with Opus codec
    silenceThreshold = 5, // Audio level below 5% is considered silence
    silenceDuration = 3000, // 3 seconds of silence triggers detection
  } = options;

  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioWorkletNodeRef = useRef<AudioWorkletNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const chunkIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const silenceStartRef = useRef<number | null>(null); // Timestamp when silence started
  const silenceCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pcmBufferRef = useRef<Int16Array[]>([]); // Buffer for PCM16 chunks
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const isRecordingRef = useRef(false); // Ref to track recording state without stale closure
  const chunkBufferRef = useRef<Int16Array[]>([]); // Buffer for combining chunks before sending
  const lastSendTimeRef = useRef<number>(0); // Throttle sending rate
  const aggregatedBufferRef = useRef<Int16Array[]>([]); // Aggregate chunks for 40ms send interval
  const aggregatedSendIntervalRef = useRef<NodeJS.Timeout | null>(null); // Interval for aggregated sends
  const CHUNK_BATCH_SIZE = 2; // Combine 2 chunks before sending (reduces WS frame count by 2x)
  const AGGREGATED_SEND_INTERVAL_MS = 40; // Send aggregated chunks every 40ms (Deepgram requires <50ms gaps)
  const MAX_BUFFERED_AMOUNT = 3000000; // Max WebSocket bufferedAmount before load-shedding (3MB - rarely triggers)

  // Convert Float32 audio samples to Int16 PCM16
  const convertToPCM16 = useCallback((float32Array: Float32Array): Int16Array => {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      // Clamp to [-1, 1] and convert to Int16 range [-32768, 32767]
      const sample = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
    }
    return int16Array;
  }, []);

  // Update audio level for visualization and silence detection
  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current || !dataArrayRef.current || !isRecording || isPaused) {
      setAudioLevel(0);
      silenceStartRef.current = null; // Reset silence timer when not recording
      return;
    }

    // Fix ArrayBufferLike vs ArrayBuffer type issue
    if (!dataArrayRef.current) return;
    // Create a new Uint8Array with explicit ArrayBuffer type
    const buffer = new ArrayBuffer(dataArrayRef.current.length);
    const dataArray = new Uint8Array(buffer);
    analyserRef.current.getByteFrequencyData(dataArray);
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
    const level = Math.round((average / 255) * 100);
    setAudioLevel(level);

    // Silence detection
    if (onSilenceDetected && silenceDuration > 0) {
      const now = Date.now();
      
      if (level < silenceThreshold) {
        // Audio level is below threshold - silence detected
        if (silenceStartRef.current === null) {
          // Start silence timer
          silenceStartRef.current = now;
        } else {
          // Check if silence duration has been reached
          const silenceTime = now - silenceStartRef.current;
          if (silenceTime >= silenceDuration) {
            // Silence threshold reached - trigger callback
            silenceStartRef.current = null; // Reset timer
            onSilenceDetected();
          }
        }
      } else {
        // Audio level is above threshold - reset silence timer
        silenceStartRef.current = null;
      }
    }

    animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
  }, [isRecording, isPaused, onSilenceDetected, silenceThreshold, silenceDuration]);

  // Request microphone permission
  const requestPermission = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: channels,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Create AudioContext for audio level analysis
      const audioContext = new AudioContext({ sampleRate });
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      dataArrayRef.current = dataArray;

      // Stop the stream - we'll get a new one when recording starts
      stream.getTracks().forEach(track => track.stop());

      setHasPermission(true);
      setError(null);
      return true;
    } catch (err: any) {
      console.error('Error requesting microphone permission:', err);
      setError(err.message || 'Failed to access microphone');
      setHasPermission(false);
      return false;
    }
  }, [sampleRate, channels]);

  // Start recording - uses AudioContext + AudioWorklet for PCM16 capture
  // AudioWorklet runs on audio thread (not main thread), preventing CPU backpressure freezes
  const startRecording = useCallback(async () => {
    // If already recording, don't start again
    if (isRecording) {
      console.log('Already recording, skipping start');
      return;
    }
    
    // Cleanup any previous recording
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (audioWorkletNodeRef.current) {
      audioWorkletNodeRef.current.disconnect();
      audioWorkletNodeRef.current = null;
    }

    if (audioSourceRef.current) {
      audioSourceRef.current.disconnect();
      audioSourceRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      // Keep AudioContext alive for reuse, but disconnect nodes
    }

    try {
      setError(null);

      // Request permission if not already granted
      if (!hasPermission) {
        const granted = await requestPermission();
        if (!granted) {
          return;
        }
      }

      // Get user media with enhanced echo cancellation
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: channels,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          // Chrome-specific constraints (use type assertion to avoid TypeScript errors)
          ...({
            googEchoCancellation: true,
            googNoiseSuppression: true,
            googAutoGainControl: true,
            googHighpassFilter: true,
            googTypingNoiseDetection: true,
          } as any),
        },
      });

      streamRef.current = stream;

      // Create or reuse AudioContext
      let audioContext = audioContextRef.current;
      if (!audioContext || audioContext.state === 'closed') {
        audioContext = new AudioContext({ sampleRate });
        audioContextRef.current = audioContext;
      } else if (audioContext.sampleRate !== sampleRate) {
        // Recreate if sample rate doesn't match
        await audioContext.close();
        audioContext = new AudioContext({ sampleRate });
        audioContextRef.current = audioContext;
      }

      // Resume AudioContext if suspended
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      // Create audio source from stream
      const source = audioContext.createMediaStreamSource(stream);
      audioSourceRef.current = source;

      // Create analyser for audio level visualization
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyserRef.current = analyser;
      dataArrayRef.current = dataArray;
      source.connect(analyser);

      // Use AudioWorklet for PCM16 capture (runs on audio thread, won't freeze on main thread)
      // This prevents CPU backpressure freezes that cause WebSocket disconnections after 3-5 minutes
      let chunkCount = 0;
      
      try {
        // Load AudioWorklet module if not already loaded
        try {
          await audioContext.audioWorklet.addModule('/pcm16-processor.js');
          console.log('✓ AudioWorklet module loaded');
        } catch (moduleError: any) {
          // Module might already be loaded, or there's an error
          if (moduleError.message && moduleError.message.includes('already been loaded')) {
            console.log('✓ AudioWorklet module already loaded');
          } else {
            throw new Error(`Failed to load AudioWorklet module: ${moduleError.message}`);
          }
        }

        // Create AudioWorkletNode
        const workletNode = new AudioWorkletNode(audioContext, 'pcm16-processor');
        audioWorkletNodeRef.current = workletNode;

        // Handle messages from worklet (PCM16 chunks)
        // Throttle and batch chunks to prevent WebSocket buffer overflow
        workletNode.port.onmessage = (event) => {
          // Use ref to check recording state (avoids stale closure)
          if (!isRecordingRef.current) {
            return;
          }

          // event.data is an ArrayBuffer containing Int16Array PCM16 data
          const int16Array = new Int16Array(event.data);
          
          chunkCount++;
          
          // Log first chunk and occasionally after
          if (chunkCount === 1 || Math.random() < 0.05) {
            console.log('🎙️ PCM16 chunk from AudioWorklet', {
              chunkNumber: chunkCount,
              size: int16Array.byteLength,
              samples: int16Array.length,
              hasCallback: !!onAudioChunk,
              isRecording: isRecordingRef.current
            });
          }

          if (onAudioChunk && int16Array.length > 0) {
            // Add to aggregated buffer (will be sent every 40ms to meet Deepgram's <50ms requirement)
            aggregatedBufferRef.current.push(int16Array);
            
            // Start aggregated send interval if not already running
            if (!aggregatedSendIntervalRef.current && isRecordingRef.current) {
              aggregatedSendIntervalRef.current = setInterval(() => {
                if (!isRecordingRef.current || aggregatedBufferRef.current.length === 0) {
                  return;
                }
                
                // Combine all aggregated chunks
                const totalSamples = aggregatedBufferRef.current.reduce((sum, arr) => sum + arr.length, 0);
                if (totalSamples === 0) {
                  aggregatedBufferRef.current = [];
                  return;
                }
                
                const combined = new Int16Array(totalSamples);
                let offset = 0;
                for (const arr of aggregatedBufferRef.current) {
                  combined.set(arr, offset);
                  offset += arr.length;
                }
                
                // Convert combined Int16Array to base64
                // Create a new ArrayBuffer to avoid SharedArrayBuffer type issues
                const buffer = combined.buffer.slice(0); // Creates a new ArrayBuffer copy
                const uint8Array = new Uint8Array(buffer);
                
                // Convert to base64 (more efficient for WebSocket)
                let binary = '';
                for (let i = 0; i < uint8Array.length; i++) {
                  binary += String.fromCharCode(uint8Array[i]);
                }
                const base64 = btoa(binary);
                
                if (base64 && base64.length > 0) {
                  onAudioChunk(base64, sampleRate, channels);
                  lastSendTimeRef.current = performance.now();
                } else {
                  console.warn('⚠️ Empty base64 data from PCM16 chunk');
                }
                
                // Clear aggregated buffer
                aggregatedBufferRef.current = [];
              }, AGGREGATED_SEND_INTERVAL_MS);
            }
          }
        };

        // Connect source to worklet node
        source.connect(workletNode);
        // AudioWorklet doesn't need to connect to destination - it processes in background
        
        console.log('✓ AudioWorklet recording started (no main thread blocking)');
      } catch (workletError: any) {
        // Fallback to ScriptProcessorNode if AudioWorklet fails (shouldn't happen in modern browsers)
        console.warn('⚠️ AudioWorklet failed, falling back to ScriptProcessorNode:', workletError);
        setError(`AudioWorklet not supported: ${workletError.message}. Please use a modern browser.`);
        throw workletError; // Don't fallback - AudioWorklet should work in all modern browsers
      }

      // Set state to true and update ref
      isRecordingRef.current = true;
      setIsRecording(true);
      setIsPaused(false);
      pcmBufferRef.current = []; // Clear buffer

      console.log('✓ PCM16 recording started successfully with AudioWorklet', {
        sampleRate,
        channels,
        method: 'AudioWorklet (no main thread blocking)'
      });

      // Start audio level updates
      updateAudioLevel();
    } catch (err: any) {
      console.error('Error starting recording:', err);
      setError(err.message || 'Failed to start recording');
      setIsRecording(false);
    }
  }, [isRecording, isPaused, hasPermission, requestPermission, sampleRate, channels, onAudioChunk, updateAudioLevel, convertToPCM16]);

  // Stop recording
  const stopRecording = useCallback((force: boolean = false) => {
    console.log('⏸️ stopRecording called', { 
      isRecording,
      force,
      stackTrace: new Error().stack?.split('\n').slice(1, 4).join('\n')
    });

    // Disconnect script processor
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.onaudioprocess = null; // Clear handler first
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    // Disconnect audio worklet node
    if (audioWorkletNodeRef.current) {
      audioWorkletNodeRef.current.disconnect();
      audioWorkletNodeRef.current = null;
    }

    // Disconnect audio source
    if (audioSourceRef.current) {
      audioSourceRef.current.disconnect();
      audioSourceRef.current = null;
    }

    // Stop all media tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
        console.log('✓ Stopped media track:', track.kind);
      });
      streamRef.current = null;
    }

    // Don't close AudioContext - keep it alive for reuse
    // Only disconnect nodes

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    if (chunkIntervalRef.current) {
      clearInterval(chunkIntervalRef.current);
      chunkIntervalRef.current = null;
    }

    if (silenceCheckIntervalRef.current) {
      clearInterval(silenceCheckIntervalRef.current);
      silenceCheckIntervalRef.current = null;
    }

    silenceStartRef.current = null; // Reset silence timer
    pcmBufferRef.current = []; // Clear buffer
    chunkBufferRef.current = []; // Clear chunk buffer
    aggregatedBufferRef.current = []; // Clear aggregated buffer
    lastSendTimeRef.current = 0; // Reset send time
    
    // Stop aggregated send interval
    if (aggregatedSendIntervalRef.current) {
      clearInterval(aggregatedSendIntervalRef.current);
      aggregatedSendIntervalRef.current = null;
    }
    
    isRecordingRef.current = false; // Update ref first
    setIsRecording(false);
    setIsPaused(false);
    setAudioLevel(0);
    
    console.log('✓ Recording stopped successfully');
    return true; // Successfully stopped
  }, [isRecording]);

  // Pause recording
  const pauseRecording = useCallback(() => {
    if (audioWorkletNodeRef.current && isRecordingRef.current) {
      // Disconnect worklet node to pause
      audioWorkletNodeRef.current.disconnect();
      if (audioSourceRef.current) {
        audioSourceRef.current.disconnect();
      }
      setIsPaused(true);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      setAudioLevel(0);
    } else if (scriptProcessorRef.current && isRecordingRef.current) {
      // Fallback for ScriptProcessorNode (shouldn't be used, but keep for compatibility)
      scriptProcessorRef.current.disconnect();
      setIsPaused(true);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      setAudioLevel(0);
    }
  }, []);

  // Resume recording
  const resumeRecording = useCallback(() => {
    if (audioWorkletNodeRef.current && audioSourceRef.current && audioContextRef.current && isPaused) {
      // Reconnect worklet node to resume
      audioSourceRef.current.connect(audioWorkletNodeRef.current);
      setIsPaused(false);
      updateAudioLevel();
    } else if (scriptProcessorRef.current && audioSourceRef.current && audioContextRef.current && isPaused) {
      // Fallback for ScriptProcessorNode (shouldn't be used, but keep for compatibility)
      audioSourceRef.current.connect(scriptProcessorRef.current);
      scriptProcessorRef.current.connect(audioContextRef.current.destination);
      setIsPaused(false);
      updateAudioLevel();
    }
  }, [isPaused, updateAudioLevel]);

  // Cleanup on unmount only - don't depend on stopRecording to avoid re-running
  useEffect(() => {
    return () => {
      // Only cleanup on unmount, not when stopRecording function changes
      if (scriptProcessorRef.current) {
        scriptProcessorRef.current.onaudioprocess = null;
        scriptProcessorRef.current.disconnect();
      }
      if (audioWorkletNodeRef.current) {
        audioWorkletNodeRef.current.port.onmessage = null;
        audioWorkletNodeRef.current.disconnect();
      }
      if (audioSourceRef.current) {
        audioSourceRef.current.disconnect();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (chunkIntervalRef.current) {
        clearInterval(chunkIntervalRef.current);
      }
      if (silenceCheckIntervalRef.current) {
        clearInterval(silenceCheckIntervalRef.current);
      }
      if (aggregatedSendIntervalRef.current) {
        clearInterval(aggregatedSendIntervalRef.current);
        aggregatedSendIntervalRef.current = null;
      }
    };
  }, []); // Empty deps - only run on mount/unmount

  return {
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    isRecording,
    isPaused,
    hasPermission,
    error,
    audioLevel,
  };
}

