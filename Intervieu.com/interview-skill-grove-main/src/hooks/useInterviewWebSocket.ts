/**
 * Manual Interview WebSocket Hook
 * - Recording is MANUAL ONLY - user clicks "Start Answering" and "Stop Answering"
 * - No automatic silence detection
 * - Echo prevention: Mic stops when TTS audio is playing
 * - Simple: Question → User clicks "Start" → Records → User clicks "Stop" → Sends to backend
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WebSocketMessage } from '../services/websocketService';
import { interviewService } from '../services/interviewService';
import { useDeepgramSTT } from './useDeepgramSTT';
import { useAudioPlayer } from './useAudioPlayer';

export interface InterviewQuestion {
  question_id: string;
  question: string;
  skill: string;
  difficulty: string;
  question_type: string;
  context?: any;
}

export interface InterviewEvaluation {
  score: number;
  feedback: string;
  strengths: string[];
  weaknesses: string[];
  next_difficulty: string;
}

export interface InterviewProgress {
  total_questions: number;
  questions_answered: number;
  current_phase: string;
  percentage: number;
}

export interface UseInterviewWebSocketOptions {
  interviewId: string;
  onQuestion?: (question: InterviewQuestion) => void;
  onEvaluation?: (evaluation: InterviewEvaluation) => void;
  onTranscript?: (text: string, isFinal: boolean) => void;
  onCompleted?: () => void;
  onError?: (error: string) => void;
  enableAudioRecording?: boolean;
  enableAudioPlayback?: boolean;
}

export interface UseInterviewWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  currentQuestion: InterviewQuestion | null;
  evaluation: InterviewEvaluation | null;
  progress: InterviewProgress | null;
  transcript: string;
  isInterviewCompleted: boolean;
  isProcessingAnswer: boolean; // True when waiting for next question after stop_recording
  sendAnswer: (answer: string, code?: string, language?: string) => void;
  sendTextAnswer: (answer: string) => void;
  sendCodeAnswer: (code: string, language: string) => void;
  reconnect: () => void;
  disconnect: () => void;
  // Manual recording controls
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  isRecording: boolean;
  audioLevel: number;
  isPlaying: boolean;
  volume: number;
  setVolume: (volume: number) => void;
}

export function useInterviewWebSocket(
  options: UseInterviewWebSocketOptions
): UseInterviewWebSocketReturn {
  const {
    interviewId,
    onQuestion,
    onEvaluation,
    onTranscript,
    onCompleted,
    onError,
    enableAudioRecording = true,
    enableAudioPlayback = true,
  } = options;

  const [currentQuestion, setCurrentQuestion] = useState<InterviewQuestion | null>(null);
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null);
  const [progress, setProgress] = useState<InterviewProgress | null>(null);
  const [transcript, setTranscript] = useState('');
  const [isInterviewCompleted, setIsInterviewCompleted] = useState(false);
  const [isProcessingAnswer, setIsProcessingAnswer] = useState(false); // True when waiting for next question
  const [deepgramApiKey, setDeepgramApiKey] = useState<string | null>(null);
  const [isLoadingDeepgramKey, setIsLoadingDeepgramKey] = useState(false);
  const transcriptRef = useRef('');
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastActivityRef = useRef<number>(Date.now());

  const wsUrl = interviewService.getWebSocketUrl(interviewId);
  
  // URL changes tracked (removed debug log)
  useEffect(() => {
    // WebSocket URL for interview tracked
  }, [interviewId, wsUrl]);

  // Fetch Deepgram API key: Check BYOK first, then env var, then backend
  useEffect(() => {
    if (enableAudioRecording && !deepgramApiKey && !isLoadingDeepgramKey) {
      // 1. Check for BYOK key first (stored in localStorage)
      const byokKey = localStorage.getItem('byok_deepgram_key');
      if (byokKey && byokKey.trim()) {
        console.log('✅ Using BYOK Deepgram API key from localStorage');
        setDeepgramApiKey(byokKey.trim());
        return;
      }

      // 2. Check for local development API key
      const localApiKey = import.meta.env.VITE_DEEPGRAM_API_KEY;
      if (localApiKey) {
        console.log('✅ Using local Deepgram API key from .env.local');
        setDeepgramApiKey(localApiKey);
        return;
      }

      // 3. Fall back to backend API (production)
      console.log('🔑 Fetching Deepgram API key from backend...');
      setIsLoadingDeepgramKey(true);
      interviewService.getDeepgramToken(interviewId)
        .then(response => {
          console.log('📦 Deepgram token response:', { hasApiKey: !!response.api_key, keys: Object.keys(response) });
          if (response.api_key) {
            console.log('✅ Deepgram API key received from backend');
            setDeepgramApiKey(response.api_key);
            setIsLoadingDeepgramKey(false);
          } else {
            console.error('❌ Deepgram token response missing api_key:', response);
            setIsLoadingDeepgramKey(false);
            onError?.('Failed to get Deepgram API key from server. Response: ' + JSON.stringify(response));
          }
        })
        .catch(err => {
          console.error('❌ Error fetching Deepgram token:', err);
          setIsLoadingDeepgramKey(false);
          onError?.('Failed to initialize speech recognition. Please check your connection and try again.');
        });
    }
  }, [enableAudioRecording, interviewId, deepgramApiKey, isLoadingDeepgramKey, onError]);

  // Direct Deepgram STT - Browser connects directly to Deepgram (no backend proxy)
  // This eliminates all the complexity of audio forwarding, batching, and buffering
  const {
    startRecording: startDeepgramRecording,
    stopRecording: stopDeepgramRecording,
    isRecording,
    audioLevel,
    accumulatedTranscript: deepgramTranscript,
    error: deepgramError,
  } = useDeepgramSTT({
    apiKey: deepgramApiKey || undefined,
    onTranscript: (text, isFinal) => {
      // Update last activity time
      lastActivityRef.current = Date.now();
      
      // Accumulate transcript internally (for backend submission) but don't display live
      // Only store final transcripts - we'll display after recording stops
      if (isFinal) {
        transcriptRef.current = transcriptRef.current ? `${transcriptRef.current} ${text}` : text;
        // Update internal state for submission, but don't call onTranscript callback
        // The callback will only be called when recording stops
      }
      // DON'T call onTranscript here - we only show transcript after recording stops
      // This prevents creating multiple bubbles during live speech recognition
    },
    onAudioActivity: () => {
      // Update last activity time when audio is being sent to Deepgram
      lastActivityRef.current = Date.now();
    },
    onError: (error) => {
      console.error('Deepgram STT error:', error);
      onError?.(error);
    },
  });

  // Audio player - Stop mic when playing to prevent echo
  const {
    play: playAudio,
    pause: pauseAudio,
    isPlaying,
    volume,
    setVolume,
    error: playerError,
  } = useAudioPlayer({
    onPlay: () => {
      // Stop recording when audio starts playing to prevent echo
      if (isRecording) {
        stopRecording();
      }
    },
    onEnded: () => {
      // Don't auto-start - user will click "Start Answering" button
    },
    volume: 1,
    autoPlay: true,
  });

  // WebSocket hook
  const {
    sendMessage,
    sendAudioChunk,
    sendAnswer: sendWebSocketAnswer,
    sendPing,
    isConnected,
    isConnecting,
    error: wsError,
    reconnect,
    disconnect,
  } = useWebSocket({
    url: wsUrl,
    onMessage: handleWebSocketMessage,
    onOpen: () => {
      // WebSocket connected
    },
    onClose: () => {
      stopRecording();
      
      // NOTE: We do NOT call disconnect() here - onClose is just a notification
      // The WebSocket is already closed, we're just cleaning up local state
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
      onError?.('WebSocket connection error');
    },
    reconnect: true,
    reconnectInterval: 5000,
    maxReconnectAttempts: 10,
  });

  // Handle WebSocket messages
  function handleWebSocketMessage(message: WebSocketMessage) {

    switch (message.type) {
      case 'connected':
        break;

      case 'question':
        if (message.question) {
          setCurrentQuestion(message.question);
          // CRITICAL: Clear processing state - next question has arrived
          setIsProcessingAnswer(false);
          onQuestion?.(message.question);
          // Don't clear transcript here - let the UI handle it when displaying the new question
          // The transcript will be cleared naturally when the new question is added to the UI
          // setTranscript('');
          // transcriptRef.current = '';

          // Play TTS audio if available (will stop mic automatically via onPlay callback)
          if (enableAudioPlayback && message.audio) {
            if (message.audio.trim().length === 0) {
              console.warn('⚠️ Received empty audio data with question, skipping playback');
            } else {
              playAudio(message.audio, message.format || 'mp3').catch((err) => {
                console.error('Error playing audio:', err);
              });
            }
          }
        }
        break;

      case 'audio':
        // Standalone audio message (TTS) - will stop mic via onPlay callback
        if (message.audio && enableAudioPlayback) {
          if (message.audio.trim().length === 0) {
            console.warn('⚠️ Received empty audio data, skipping playback');
          } else {
            playAudio(message.audio, message.format || 'mp3').catch((err) => {
              console.error('❌ Error playing audio:', err);
            });
          }
        }
        break;

      case 'transcript':
        if (message.text !== undefined) {
          // Backend sends accumulated transcript - always update it
          const transcriptText = message.text || '';
          setTranscript(transcriptText);
          transcriptRef.current = transcriptText;
          onTranscript?.(transcriptText, message.is_final || false);
        }
        break;

      case 'evaluation':
        if (message.evaluation) {
          setEvaluation(message.evaluation);
          onEvaluation?.(message.evaluation);
          setTranscript('');
          transcriptRef.current = '';
        }
        break;

      case 'completed':
        setIsInterviewCompleted(true);
        setIsProcessingAnswer(false); // Clear processing state
        stopRecording();
        // NOTE: Do NOT disconnect WebSocket here - keep it alive for potential resume/reconnect
        // Only disconnect explicitly when user navigates away or ends interview
        onCompleted?.();
        break;

      case 'error':
        // Clear processing state on error so user can try again
        setIsProcessingAnswer(false);
        onError?.(message.message || 'Unknown error');
        break;

      case 'resume':
        if (message.interview_state) {
          setProgress({
            total_questions: message.interview_state.max_questions || 12,
            questions_answered: message.interview_state.total_questions || 0,
            current_phase: message.interview_state.current_phase || 'introduction',
            percentage: message.interview_state.progress?.percentage || 0,
          });
          // Restore interview state after page refresh
        }
        break;

      case 'flow_state':
        // Handle flow state changes (e.g., after page refresh)
        if (message.state) {
          // If flow_state is 'user_speaking' and no current question, user should be ready to answer
          // But don't auto-start recording - user must click "Start Answering"
        }
        break;

      default:
        break;
    }
  }

  // Manual start recording - called by user clicking "Start Answering" button
  // Simplified startRecording using direct Deepgram STT
  const startRecording = useCallback(async () => {
    if (!enableAudioRecording) {
      return;
    }

    if (!isConnected) {
      console.warn('Cannot start recording: WebSocket is not connected');
      onError?.('WebSocket is not connected');
      return;
    }

    if (isRecording) {
      return;
    }

    if (isPlaying) {
      console.warn('Cannot start recording: Audio is still playing');
      onError?.('Please wait for audio to finish playing');
      return;
    }

    if (!deepgramApiKey) {
      if (isLoadingDeepgramKey) {
        console.warn('Cannot start recording: Deepgram API key is still loading...');
        onError?.('Speech recognition is initializing... Please wait a moment.');
      } else {
        console.warn('Cannot start recording: Deepgram API key not available');
        onError?.('Speech recognition failed to initialize. Please refresh the page and try again.');
      }
      return;
    }

    try {
      
      // Clear previous transcript
      setTranscript('');
      transcriptRef.current = '';
      lastActivityRef.current = Date.now();
      
      // Start Deepgram recording - connects directly to Deepgram
      await startDeepgramRecording();
      
      // Start ping interval to keep WebSocket alive during long answers
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      
      pingIntervalRef.current = setInterval(() => {
        const timeSinceActivity = Date.now() - lastActivityRef.current;
        
        // Send ping every 10 seconds to keep WebSocket alive
        if (isConnected && sendPing) {
          sendPing();
        }
      }, 10000); // Ping every 10 seconds
    } catch (error: any) {
      console.error('✗ Error starting recording:', error);
      onError?.(error.message || 'Failed to start recording');
    }
  }, [enableAudioRecording, isConnected, isRecording, isPlaying, deepgramApiKey, startDeepgramRecording, sendPing, onError]);

  // Simplified stopRecording using direct Deepgram STT
  const stopRecording = useCallback(() => {
    if (!isRecording) {
      return;
    }
    
    // Stop ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    
    // Stop Deepgram recording
    stopDeepgramRecording();
    
    // Send the accumulated transcript to the backend for evaluation
    const currentTranscript = deepgramTranscript || transcriptRef.current || transcript;
    
    if (isConnected && currentTranscript) {
      
      // Set processing state to disable "Start Answering" button until next question arrives
      setIsProcessingAnswer(true);
      
      // Display the final answer in the UI (single bubble, only after recording stops)
      // This is the only time we show the transcript to the user
      onTranscript?.(currentTranscript.trim(), true);
      
      sendMessage({
        type: 'submit_answer',
        data: {
          interview_id: interviewId,
          answer: currentTranscript.trim(),
        }
      });
      
      // Clear local transcript storage (for next answer)
      setTranscript('');
      transcriptRef.current = '';
    } else if (!currentTranscript) {
      console.warn('⚠️ No transcript to submit');
      onError?.('No audio was captured. Please try again.');
    }

  }, [interviewId, isRecording, deepgramTranscript, transcript, stopDeepgramRecording, isConnected, sendMessage, onError, onTranscript]);

  // Stop mic when interview completes
  useEffect(() => {
    if (isInterviewCompleted) {
      stopRecording();
    }
  }, [isInterviewCompleted, stopRecording]);

  // Cleanup ping interval on unmount
  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
    };
  }, []);

  // Send answer (for text/code submission)
  const sendAnswer = useCallback((answer: string, code?: string, language?: string) => {
    if (!isConnected) {
      onError?.('WebSocket is not connected');
      return;
    }
    sendWebSocketAnswer(answer, code, language);
    // Don't clear transcript here - let the UI handle it
    // The transcript is already added in InterviewInterface before calling this
    // setTranscript('');
    // transcriptRef.current = '';
  }, [isConnected, sendWebSocketAnswer, onError]);

  const sendTextAnswer = useCallback((answer: string) => {
    sendAnswer(answer);
  }, [sendAnswer]);

  const sendCodeAnswer = useCallback((code: string, language: string) => {
    sendAnswer('', code, language);
  }, [sendAnswer]);

  const error = wsError || deepgramError || playerError || null;

  return {
    isConnected,
    isConnecting,
    error,
    currentQuestion,
    evaluation,
    progress,
    transcript,
    isInterviewCompleted,
    isProcessingAnswer, // True when waiting for next question after stop_recording
    sendAnswer,
    sendTextAnswer,
    sendCodeAnswer,
    reconnect,
    disconnect,
    // Manual recording controls
    startRecording,
    stopRecording,
    isRecording,
    audioLevel,
    isPlaying,
    volume,
    setVolume,
  };
}
