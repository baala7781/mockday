
import React, { useRef, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';

interface VideoFeedProps {
  muted?: boolean;
  mirrored?: boolean;
  className?: string;
}

const VideoFeed: React.FC<VideoFeedProps> = ({ 
  muted = false, 
  mirrored = true,
  className = "" 
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasPermission, setHasPermission] = useState(true);

  useEffect(() => {
    let stream: MediaStream | null = null;

    const setupCamera = async () => {
      try {
        setIsLoading(true);
        // ALWAYS mute audio in video feed to prevent echo
        // Audio is handled separately by useAudioRecorder for STT
        stream = await navigator.mediaDevices.getUserMedia({ 
          video: true, 
          audio: false  // Always disable audio - prevents echo/feedback
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        
        setHasPermission(true);
      } catch (error) {
        console.error('Error accessing camera:', error);
        setHasPermission(false);
      } finally {
        setIsLoading(false);
      }
    };

    setupCamera();

    // Cleanup
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [muted]);

  return (
    <div className={`relative w-full h-full rounded-2xl overflow-hidden bg-black ${className}`}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
        </div>
      )}
      
      {!hasPermission && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-background/80 backdrop-blur-sm">
          <p className="text-foreground mb-2">Camera access is required</p>
          <Button 
            size="sm"
            onClick={() => setHasPermission(true)}
          >
            Enable camera
          </Button>
        </div>
      )}
      
      <video 
        ref={videoRef}
        autoPlay 
        playsInline
        muted={muted}
        className={`h-full w-full object-cover rounded-2xl ${mirrored ? 'scale-x-[-1]' : ''}`}
        onLoadedData={() => setIsLoading(false)}
      />

      <div className="absolute bottom-3 left-3 px-2 py-1 bg-background/80 backdrop-blur-sm rounded-md text-foreground text-xs border border-border">
        {muted ? 'Muted' : 'Live'}
      </div>
    </div>
  );
};

export default VideoFeed;
