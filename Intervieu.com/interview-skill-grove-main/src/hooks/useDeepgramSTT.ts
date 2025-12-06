/**
 * Direct Deepgram STT Hook
 * Connects browser directly to Deepgram for real-time speech-to-text
 * This eliminates the backend audio proxy and simplifies the architecture
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { createClient, LiveTranscriptionEvents, LiveClient } from '@deepgram/sdk';

export interface UseDeepgramSTTOptions {
  onTranscript?: (text: string, isFinal: boolean) => void;
  onError?: (error: string) => void;
  onAudioActivity?: () => void; // Called when audio is being processed (for keepalive)
  apiKey?: string; // Temporary API key from backend
}

export interface UseDeepgramSTTReturn {
  isConnected: boolean;
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  accumulatedTranscript: string;
  audioLevel: number;
  error: string | null;
}

export function useDeepgramSTT(options: UseDeepgramSTTOptions): UseDeepgramSTTReturn {
  const { onTranscript, onError, onAudioActivity, apiKey } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [accumulatedTranscript, setAccumulatedTranscript] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const connectionRef = useRef<any>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  const startRecording = useCallback(async () => {
    if (!apiKey) {
      const err = 'No Deepgram API key provided';
      setError(err);
      onError?.(err);
      return;
    }

    try {
      console.log('🎤 Starting direct Deepgram STT...');

      // Create Deepgram client
      const deepgram = createClient(apiKey);

      // Connect to Deepgram Live
      const connection = deepgram.listen.live({
        model: 'nova-3',
        language: 'en-US',
        smart_format: true,
        interim_results: true,
        encoding: 'linear16',
        sample_rate: 16000,
        channels: 1,
      });
      
      connectionRef.current = connection;

      // Handle Deepgram events
      connection.on(LiveTranscriptionEvents.Open, () => {
        console.log('✓ Deepgram connection opened');
        setIsConnected(true);
      });

      connection.on(LiveTranscriptionEvents.Transcript, (data: any) => {
        try {
          const transcript = data.channel?.alternatives?.[0]?.transcript;
          const isFinal = data.is_final || false;

          if (transcript && transcript.trim()) {
            console.log('📝 Deepgram transcript:', { transcript: transcript.substring(0, 50), isFinal });
            
            // Update accumulated transcript
            if (isFinal) {
              setAccumulatedTranscript(prev => prev ? `${prev} ${transcript}` : transcript);
            }
            
            // Call callback
            onTranscript?.(transcript, isFinal);
          }
        } catch (err) {
          console.error('Error processing Deepgram transcript:', err);
        }
      });

      connection.on(LiveTranscriptionEvents.Error, (err: any) => {
        console.error('Deepgram error:', err);
        const errorMsg = err.message || 'Deepgram connection error';
        setError(errorMsg);
        onError?.(errorMsg);
      });

      connection.on(LiveTranscriptionEvents.Close, () => {
        console.log('Deepgram connection closed');
        setIsConnected(false);
      });

      // Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1,
        },
      });
      mediaStreamRef.current = stream;

      // Setup audio processing to convert to PCM16
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      
      // Create analyser for audio level monitoring
      const analyser = audioContext.createAnalyser();
      analyserRef.current = analyser;
      analyser.fftSize = 256;
      source.connect(analyser);

      // Create script processor to convert Float32 to Int16 PCM
      const processor = audioContext.createScriptProcessor(2048, 1, 1);
      processorRef.current = processor;
      
      processor.onaudioprocess = (e) => {
        if (!connectionRef.current || connectionRef.current.getReadyState() !== 1) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Send PCM16 data to Deepgram
        connectionRef.current.send(pcm16.buffer);
        
        // Notify parent about audio activity (for WebSocket keepalive)
        onAudioActivity?.();
      };
      
      source.connect(processor);
      processor.connect(audioContext.destination);

      // Audio level monitoring
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateAudioLevel = () => {
        if (!analyserRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        setAudioLevel(Math.min(100, (average / 128) * 100));
        animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
      };
      updateAudioLevel();

      setIsRecording(true);
      setAccumulatedTranscript(''); // Clear previous transcript
      console.log('✓ Direct Deepgram STT started');
    } catch (err: any) {
      console.error('Error starting Deepgram STT:', err);
      const errorMsg = err.message || 'Failed to start recording';
      setError(errorMsg);
      onError?.(errorMsg);
      // Cleanup on error
      stopRecording();
    }
  }, [apiKey, onTranscript, onError]);

  const stopRecording = useCallback(() => {
    console.log('⏸️ Stopping direct Deepgram STT...');

    // Cancel animation frame
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    // Disconnect processor
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }

    // Stop media stream
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Close Deepgram connection
    if (connectionRef.current) {
      try {
        connectionRef.current.finish();
        connectionRef.current = null;
      } catch (err) {
        console.error('Error closing Deepgram connection:', err);
      }
    }

    setIsRecording(false);
    setIsConnected(false);
    setAudioLevel(0);
    console.log('✓ Direct Deepgram STT stopped');
  }, []);

  return {
    isConnected,
    isRecording,
    startRecording,
    stopRecording,
    accumulatedTranscript,
    audioLevel,
    error,
  };
}

