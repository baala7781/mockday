/**
 * WebSocket service for real-time interview communication
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: 'audio_chunk' | 'answer' | 'stop_recording' | 'submit_answer' | 'ping' | 'question' | 'transcript' | 'evaluation' | 'audio' | 'completed' | 'error' | 'pong' | 'connected' | 'resume' | 'connection_replaced' | 'speech_end' | 'tts_end' | 'flow_state';
  data?: any;
  text?: string;
  question?: any;
  evaluation?: any;
  audio?: string;
  format?: string;
  message?: string;
  reason?: string; // For 'connection_replaced' message type
  state?: string; // For 'flow_state' message type
  is_final?: boolean;
  confidence?: number;
  interview_id?: string;
  interview_state?: any;
}

export interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export interface UseWebSocketReturn {
  sendMessage: (message: WebSocketMessage) => void;
  sendAudioChunk: (chunk: string, sampleRate: number, channels: number) => void;
  sendAnswer: (answer: string, code?: string, language?: string) => void;
  sendPing: () => void;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

/**
 * Hook for WebSocket communication
 */
export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect: shouldReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(shouldReconnect);
  const audioChunkLoggedRef = useRef(false);
  const connectionGuardRef = useRef(false); // Prevents duplicate connections

  // Update shouldReconnect ref when prop changes
  useEffect(() => {
    shouldReconnectRef.current = shouldReconnect;
  }, [shouldReconnect]);

  const connect = useCallback(() => {
    // CRITICAL: Prevent duplicate connections with guard ref
    if (connectionGuardRef.current) {
      console.warn('⚠️ [WS Guard] Connection creation blocked - connection guard is active');
      return; // Another connection is being created or is active
    }
    
    // Check connection state - don't connect if already connected or connecting
    if (wsRef.current) {
      const readyState = wsRef.current.readyState;
      if (readyState === WebSocket.OPEN) {
        console.log('[WS Guard] WebSocket already connected, skipping');
        return; // Already connected
      }
      if (readyState === WebSocket.CONNECTING) {
        console.log('[WS Guard] WebSocket already connecting, skipping');
        return; // Already connecting
      }
      // If CLOSING or CLOSED, clear the ref so we can create a new connection
      if (readyState === WebSocket.CLOSING || readyState === WebSocket.CLOSED) {
        console.log('[WS Guard] WebSocket in closing/closed state, clearing ref');
        wsRef.current = null;
        connectionGuardRef.current = false; // Release guard
      }
    }

    if (isConnecting) {
      console.log('[WS Guard] Connection already in progress, skipping');
      return; // Already connecting
    }

    // Set guard to prevent duplicate connections
    connectionGuardRef.current = true;
    
    // CRITICAL: Log stack trace to identify where WebSocket creation is triggered
    const stackTrace = new Error().stack;
    console.log('[WS] ⚠️ ATTEMPT TO CREATE WEBSOCKET - Stack trace:', stackTrace);
    console.log('[WS] Creating new WebSocket connection...', { url });
    setIsConnecting(true);
    setError(null);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      console.log('[WS] ✓ WebSocket instance created', { url, readyState: ws.readyState });

      ws.onopen = () => {
        console.log('[WS] ✓ WebSocket connected successfully');
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
        // Keep guard active while connected
        connectionGuardRef.current = true;
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          // CRITICAL: Handle both string and Blob/ArrayBuffer data
          let data: string;
          if (typeof event.data === 'string') {
            data = event.data;
          } else if (event.data instanceof Blob) {
            // Convert Blob to text (shouldn't happen for JSON, but handle gracefully)
            console.warn('[WS] Received Blob data instead of string, skipping');
            return;
          } else if (event.data instanceof ArrayBuffer) {
            // Convert ArrayBuffer to text (shouldn't happen for JSON, but handle gracefully)
            console.warn('[WS] Received ArrayBuffer data instead of string, skipping');
            return;
          } else {
            data = String(event.data);
          }
          
          // Check if data is empty or incomplete
          if (!data || data.trim().length === 0) {
            console.warn('[WS] Received empty message, skipping');
            return;
          }
          
          // Try to parse JSON
          const message: WebSocketMessage = JSON.parse(data);
          
          // Handle connection_replaced message from server
          if (message.type === 'connection_replaced') {
            console.log('Server notified: Connection replaced', message.message);
            // Server is closing this connection intentionally, don't reconnect
            shouldReconnectRef.current = false;
            // Close this connection gracefully
            if (wsRef.current) {
              wsRef.current.close(1000, 'Connection replaced');
            }
            return;
          }
          
          onMessage?.(message);
        } catch (err) {
          // CRITICAL: Log the actual data that failed to parse for debugging
          const dataPreview = typeof event.data === 'string' 
            ? event.data.substring(0, 100) 
            : `[${typeof event.data}]`;
          console.error('[WS] Error parsing WebSocket message:', err, 'Data preview:', dataPreview);
          // Don't close connection - might be a transient issue
        }
      };

      ws.onclose = (event) => {
        // Release guard when connection closes
        connectionGuardRef.current = false;
        
        // CRITICAL: Log stack trace to see what triggered the close
        const closeStackTrace = new Error().stack;
        console.log('🔌 [WS CLOSED] WebSocket closed', { 
          code: event.code, 
          reason: event.reason || 'No reason provided', 
          wasClean: event.wasClean,
          codeMeaning: event.code === 1006 ? 'Abnormal closure (browser/network issue)' : 
                       event.code === 1000 ? 'Normal closure' :
                       event.code === 1001 ? 'Going away' :
                       event.code === 1002 ? 'Protocol error' :
                       event.code === 1003 ? 'Unsupported data' :
                       event.code === 1008 ? 'Policy violation (duplicate connection rejected)' :
                       event.code === 1011 ? 'Server error' :
                       'Unknown code',
          stackTrace: closeStackTrace
        });
        setIsConnected(false);
        setIsConnecting(false);
        wsRef.current = null;
        onClose?.();

        // Don't reconnect on normal closure (code 1000) unless it's unexpected
        // Code 1000 with reason "New connection" means server intentionally replaced this connection
        const isNormalClosure = event.code === 1000;
        const isIntentionalReplacement = event.reason === 'New connection' || event.reason === 'Connection cleanup';
        const shouldNotReconnect = isNormalClosure && isIntentionalReplacement;

        if (shouldNotReconnect) {
          console.log('WebSocket closed intentionally by server (new connection), not reconnecting');
          shouldReconnectRef.current = false; // Stop reconnection attempts
          return;
        }

        // Don't reconnect on certain error codes or when server intentionally replaces connection
        // Code 1001 with reason "New connection established" means server replaced this connection
        const isConnectionReplaced = event.code === 1001 && 
                                     (event.reason === 'New connection established' || 
                                      event.reason === 'New connection');
        const errorCodesToNotReconnect = [1002, 1008, 1011]; // Protocol error, policy violation, server error
        const shouldNotReconnectOnError = errorCodesToNotReconnect.includes(event.code);
        
        if (isConnectionReplaced || shouldNotReconnectOnError) {
          if (isConnectionReplaced) {
            console.log('WebSocket connection replaced by server (new connection established), not reconnecting');
          } else {
            console.log(`WebSocket closed with error code ${event.code}, not reconnecting`);
            setError(`WebSocket error: ${event.reason || `Code ${event.code}`}`);
          }
          shouldReconnectRef.current = false;
          return;
        }

        // Attempt to reconnect if needed (only for unexpected closures)
        if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          // Exponential backoff: delay increases with each attempt
          const delay = reconnectInterval * Math.pow(2, reconnectAttemptsRef.current - 1);
          console.log(`Attempting to reconnect (${reconnectAttemptsRef.current}/${maxReconnectAttempts}) in ${delay}ms...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (shouldReconnectRef.current) { // Check again before reconnecting
              connect();
            }
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log('Max reconnection attempts reached');
          setError('Max reconnection attempts reached');
          shouldReconnectRef.current = false;
        }
      };

      ws.onerror = (event) => {
        // Release guard on error
        connectionGuardRef.current = false;
        
        // Enhanced error logging to diagnose WebSocket issues
        console.error('❌ [WS] WebSocket error event:', {
          type: event.type,
          target: event.target,
          readyState: (event.target as WebSocket)?.readyState,
          url: (event.target as WebSocket)?.url,
          message: 'WebSocket error occurred - check network, browser console, or server logs'
        });
        setError('WebSocket connection error');
        onError?.(event);
      };
    } catch (err) {
      // Release guard on exception
      connectionGuardRef.current = false;
      console.error('[WS] Error creating WebSocket:', err);
      setError('Failed to create WebSocket connection');
      setIsConnecting(false);
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnectInterval, maxReconnectAttempts, isConnecting]);

  const disconnect = useCallback(() => {
    // CRITICAL: Log when disconnect is called
    const disconnectStackTrace = new Error().stack;
    console.log('[WS MANUAL CLOSE] disconnect() called - Stack trace:', disconnectStackTrace);
    
    shouldReconnectRef.current = false;
    connectionGuardRef.current = false; // Release guard on disconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      console.log('[WS MANUAL CLOSE] Closing WebSocket explicitly');
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  const reconnect = useCallback(() => {
    // CRITICAL: Log when reconnect is called
    const stackTrace = new Error().stack;
    console.log('[WS] ⚠️ RECONNECT CALLED - Stack trace:', stackTrace);
    console.log('[WS] Reconnect triggered - current state:', {
      isConnected,
      isConnecting,
      readyState: wsRef.current?.readyState,
      url
    });
    disconnect();
    reconnectAttemptsRef.current = 0;
    shouldReconnectRef.current = true;
    connect();
  }, [connect, disconnect, isConnected, isConnecting, url]);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
      setError('WebSocket is not connected');
    }
  }, []);

  const sendAudioChunk = useCallback((chunk: string, sampleRate: number = 16000, channels: number = 1) => {
    if (!chunk || chunk.length === 0) {
      console.warn('⚠️ Attempted to send empty audio chunk');
      return;
    }
    
    // CRITICAL: Check WebSocket bufferedAmount to prevent buffer overflow (code 1006)
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const bufferedAmount = wsRef.current.bufferedAmount;
      // Increased to 3MB to prevent excessive chunk skipping that creates audio gaps
      // Only skip if buffer is truly overloaded (very rare in practice)
      const BACKPRESSURE_LIMIT_BYTES = 3_000_000; // 3MB threshold
      if (bufferedAmount > BACKPRESSURE_LIMIT_BYTES) {
        console.warn(`⚠️ [WS Backpressure] WebSocket buffer overload: ${(bufferedAmount / 1024 / 1024).toFixed(2)}MB - skipping chunk to prevent 1006 disconnect`);
        // Load-shedding: drop this chunk to prevent buffer overflow (should be very rare)
        return;
      }
      
      // Log buffer level occasionally for monitoring (not a warning unless > 1MB)
      if (bufferedAmount > 1_000_000 && (!audioChunkLoggedRef.current || Math.random() < 0.1)) {
        console.log(`📊 [WS Buffer] ${(bufferedAmount / 1024 / 1024).toFixed(2)}MB buffered (${((bufferedAmount / BACKPRESSURE_LIMIT_BYTES) * 100).toFixed(1)}% of limit)`);
      }
      
      // Log occasionally with buffer info
      if (!audioChunkLoggedRef.current || Math.random() < 0.05) {
        console.log('📡 [WS] Sending audio_chunk', {
          chunkLength: chunk.length,
          sampleRate,
          channels,
          bufferedAmount: `${(bufferedAmount / 1024).toFixed(1)}KB`,
          isConnected: true
        });
        audioChunkLoggedRef.current = true;
      }
    } else {
      console.warn('⚠️ WebSocket not ready for audio chunk', {
        readyState: wsRef.current?.readyState
      });
      return;
    }
    
    sendMessage({
      type: 'audio_chunk',
      data: {
        chunk,
        sample_rate: sampleRate,
        channels,
      },
    });
  }, [sendMessage]);

  const sendAnswer = useCallback((answer: string, code?: string, language?: string) => {
    sendMessage({
      type: 'answer',
      data: {
        answer,
        code,
        language,
      },
    });
  }, [sendMessage]);

  const sendPing = useCallback(() => {
    sendMessage({ type: 'ping' });
  }, [sendMessage]);

  // Connect on mount and when URL changes
  useEffect(() => {
    // Only connect if URL is available
    if (!url) {
      console.log('[WS Effect] No URL provided, skipping connection');
      return;
    }

    // Don't connect if already connected or connecting
    if (wsRef.current) {
      const readyState = wsRef.current.readyState;
      if (readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) {
        console.log('[WS Effect] WebSocket already connected/connecting, skipping', { readyState });
        return; // Already connected or connecting
      }
    }

    if (isConnecting) {
      console.log('[WS Effect] Connection already in progress, skipping');
      return; // Already connecting
    }

    // CRITICAL: Log when useEffect triggers connection
    console.log('[WS Effect] ⚠️ useEffect triggered connect() - Stack trace:', new Error().stack);
    console.log('[WS Effect] URL:', url, 'isConnecting:', isConnecting, 'isConnected:', isConnected);
    
    // Connect
    connect();

    // CRITICAL FIX: Do NOT close WebSocket on cleanup/unmount
    // WebSocket should persist across re-renders and only close explicitly
    // This prevents React state updates (like transcript callbacks) from closing the connection
    return () => {
      const cleanupStackTrace = new Error().stack;
      console.log('[WS Effect] ⚠️ Cleanup triggered - BUT NOT CLOSING WEBSOCKET', { 
        url,
        reason: 'WebSocket should persist across re-renders. Only close explicitly when interview ends.',
        stackTrace: cleanupStackTrace
      });
      
      // Only stop reconnection attempts, but DON'T close the WebSocket
      // The WebSocket will stay alive even if component unmounts/re-renders
      shouldReconnectRef.current = false;
      
      // Clear reconnection timeout, but keep WebSocket alive
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      // DO NOT close WebSocket here - it should persist
      // Only disconnect() should close it explicitly
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]); // Only depend on URL

  return {
    sendMessage,
    sendAudioChunk,
    sendAnswer,
    sendPing,
    isConnected,
    isConnecting,
    error,
    reconnect,
    disconnect,
  };
}

/**
 * WebSocket service class (alternative to hook)
 */
export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 3000;
  private shouldReconnect = true;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  constructor(url: string) {
    this.url = url;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.emit('open');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.emit('message', message);
            this.emit(message.type, message);
          } catch (err) {
            console.error('Error parsing WebSocket message:', err);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket closed', event.code, event.reason);
          this.emit('close');
          this.ws = null;

          if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts += 1;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => this.connect(), this.reconnectInterval);
          }
        };

        this.ws.onerror = (event) => {
          console.error('WebSocket error:', event);
          this.emit('error', event);
          reject(event);
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }

  sendAudioChunk(chunk: string, sampleRate: number = 16000, channels: number = 1): void {
    this.send({
      type: 'audio_chunk',
      data: {
        chunk,
        sample_rate: sampleRate,
        channels,
      },
    });
  }

  sendAnswer(answer: string, code?: string, language?: string): void {
    this.send({
      type: 'answer',
      data: {
        answer,
        code,
        language,
      },
    });
  }

  sendPing(): void {
    this.send({ type: 'ping' });
  }

  on(event: string, callback: (data: any) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }

  off(event: string, callback: (data: any) => void): void {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data?: any): void {
    this.listeners.get(event)?.forEach((callback) => callback(data));
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

