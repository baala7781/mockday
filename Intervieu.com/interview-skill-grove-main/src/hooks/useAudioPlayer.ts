/**
 * Hook for playing audio from base64 encoded audio data
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export interface UseAudioPlayerOptions {
  onPlay?: () => void;
  onPause?: () => void;
  onEnded?: () => void;
  onError?: (error: Error) => void;
  volume?: number; // 0-1
  autoPlay?: boolean;
}

export interface UseAudioPlayerReturn {
  play: (audioBase64: string, format?: string) => Promise<void>;
  pause: () => void;
  stop: () => void;
  setVolume: (volume: number) => void;
  isPlaying: boolean;
  isPaused: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  error: string | null;
}

export function useAudioPlayer(options: UseAudioPlayerOptions = {}): UseAudioPlayerReturn {
  const {
    onPlay,
    onPause,
    onEnded,
    onError,
    volume: initialVolume = 1,
    autoPlay = false,
  } = options;

  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(initialVolume);
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timeUpdateIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Update current time
  const updateTime = useCallback(() => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      setDuration(audioRef.current.duration || 0);
    }
  }, []);

  // Set up audio event listeners
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handlePlay = () => {
      setIsPlaying(true);
      setIsPaused(false);
      onPlay?.();

      // Start time update interval
      timeUpdateIntervalRef.current = setInterval(updateTime, 100);
    };

    const handlePause = () => {
      setIsPlaying(false);
      setIsPaused(true);
      onPause?.();

      // Stop time update interval
      if (timeUpdateIntervalRef.current) {
        clearInterval(timeUpdateIntervalRef.current);
        timeUpdateIntervalRef.current = null;
      }
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setIsPaused(false);
      setCurrentTime(0);
      onEnded?.();

      // Stop time update interval
      if (timeUpdateIntervalRef.current) {
        clearInterval(timeUpdateIntervalRef.current);
        timeUpdateIntervalRef.current = null;
      }
    };

    const handleError = () => {
      const errorMsg = audio.error?.message || 'Audio playback error';
      setError(errorMsg);
      setIsPlaying(false);
      setIsPaused(false);
      onError?.(new Error(errorMsg));
    };

    const handleTimeUpdate = () => {
      updateTime();
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration || 0);
    };

    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);

    return () => {
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [onPlay, onPause, onEnded, onError, updateTime]);

  // Set volume
  const setVolume = useCallback((newVolume: number) => {
    const clampedVolume = Math.max(0, Math.min(1, newVolume));
    setVolumeState(clampedVolume);
    if (audioRef.current) {
      audioRef.current.volume = clampedVolume;
    }
  }, []);

  // Play audio from base64
  const play = useCallback(async (audioBase64: string, format: string = 'mp3') => {
    try {
      setError(null);

      // Validate audio data
      if (!audioBase64 || typeof audioBase64 !== 'string' || audioBase64.trim().length === 0) {
        const error = new Error('Empty or invalid audio data');
        console.error('❌ Cannot play audio:', error.message);
        setError(error.message);
        onError?.(error);
        throw error;
      }

      // Decode base64 to blob
      let byteCharacters: string;
      try {
        byteCharacters = atob(audioBase64);
      } catch (e) {
        const error = new Error('Invalid base64 audio data');
        console.error('❌ Cannot decode audio:', error.message);
        setError(error.message);
        onError?.(error);
        throw error;
      }

      if (byteCharacters.length === 0) {
        const error = new Error('Decoded audio data is empty');
        console.error('❌ Cannot play audio:', error.message);
        setError(error.message);
        onError?.(error);
        throw error;
      }

      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: `audio/${format}` });

      if (blob.size === 0) {
        const error = new Error('Audio blob is empty');
        console.error('❌ Cannot play audio:', error.message);
        setError(error.message);
        onError?.(error);
        throw error;
      }

      // Create object URL
      const url = URL.createObjectURL(blob);

      if (!url || url === '') {
        const error = new Error('Failed to create audio URL');
        console.error('❌ Cannot play audio:', error.message);
        setError(error.message);
        onError?.(error);
        throw error;
      }

      // Create or update audio element
      if (!audioRef.current) {
        audioRef.current = new Audio();
        audioRef.current.volume = volume;
      } else {
        // Stop current playback if any
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        // Clear previous src if exists
        if (audioRef.current.src) {
          URL.revokeObjectURL(audioRef.current.src);
        }
      }

      audioRef.current.src = url;
      audioRef.current.volume = volume;

      // Play audio - wait for it to load first
      console.log('Loading audio...', { url: url.substring(0, 50) + '...' });
      
      // Wait for audio to be ready
      return new Promise<void>((resolve, reject) => {
        if (!audioRef.current) {
          reject(new Error('Audio element not created'));
          return;
        }

        const audio = audioRef.current;
        let loaded = false;

        const handleCanPlay = () => {
          if (!loaded) {
            loaded = true;
            console.log('Audio can play - starting playback');
            audio.play()
              .then(() => {
                console.log('✓ Audio playback started');
                resolve();
              })
              .catch((playError) => {
                console.error('Error starting playback:', playError);
                reject(playError);
              });
          }
        };

        const handleError = () => {
          const errorMsg = audio.error?.message || 'Audio load error';
          console.error('Audio load error:', errorMsg, audio.error);
          audio.removeEventListener('canplay', handleCanPlay);
          audio.removeEventListener('error', handleError);
          reject(new Error(errorMsg));
        };

        audio.addEventListener('canplay', handleCanPlay, { once: true });
        audio.addEventListener('error', handleError, { once: true });

        // Load the audio
        audio.load();

        // Timeout after 5 seconds
        setTimeout(() => {
          if (!loaded) {
            audio.removeEventListener('canplay', handleCanPlay);
            audio.removeEventListener('error', handleError);
            reject(new Error('Audio load timeout'));
          }
        }, 5000);
      });
    } catch (err: any) {
      console.error('Error playing audio:', err);
      setError(err.message || 'Failed to play audio');
      setIsPlaying(false);
      setIsPaused(false);
      onError?.(err);
      throw err; // Re-throw so caller knows it failed
    }
  }, [volume, autoPlay, onError]);

  // Pause audio
  const pause = useCallback(() => {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
    }
  }, []);

  // Stop audio
  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
      setIsPaused(false);
      setCurrentTime(0);

      // Stop time update interval
      if (timeUpdateIntervalRef.current) {
        clearInterval(timeUpdateIntervalRef.current);
        timeUpdateIntervalRef.current = null;
      }
    }
  }, []);

  // Update volume when it changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume;
    }
  }, [volume]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
      if (audioRef.current) {
        audioRef.current.src = '';
      }
      if (timeUpdateIntervalRef.current) {
        clearInterval(timeUpdateIntervalRef.current);
      }
    };
  }, [stop]);

  return {
    play,
    pause,
    stop,
    setVolume,
    isPlaying,
    isPaused,
    currentTime,
    duration,
    volume,
    error,
  };
}

