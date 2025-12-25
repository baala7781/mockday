
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CheckCircle2, XCircle, Video, Mic, AlertTriangle } from 'lucide-react';

const HardwareCheck: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const interviewId = searchParams.get('interviewId') || searchParams.get('id'); // Support both for backward compatibility

  const [cameraPermission, setCameraPermission] = useState<boolean | null>(null);
  const [micPermission, setMicPermission] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    const checkPermissions = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        
        // Only update state if component is still mounted
        if (!isMounted) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }
        
        streamRef.current = stream;
        
        // Check for tracks to be more certain
        setCameraPermission(stream.getVideoTracks().length > 0);
        setMicPermission(stream.getAudioTracks().length > 0);

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

      } catch (err) {
        // Only update state if component is still mounted
        if (!isMounted) return;
        
        console.error("Error accessing media devices:", err);
        if (err instanceof DOMException) {
            if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                setError("Permissions for camera and microphone were denied. Please enable them in your browser settings to continue.");
            } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
                setError("No camera or microphone found. Please ensure they are connected and enabled.");
            } else {
                setError("An unknown error occurred while accessing your camera and microphone.");
            }
        } else {
             setError("An unexpected error occurred. Please try again.");
        }
        setCameraPermission(false);
        setMicPermission(false);
      }
    };

    checkPermissions();
    
    // Cleanup function to stop media tracks when component unmounts
    return () => {
        isMounted = false;
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = null;
        }
    };

  }, []);

  const allPermissionsGranted = cameraPermission && micPermission;

  const handleStartInterview = () => {
    if (interviewId) {
      navigate(`/interview?interviewId=${interviewId}`);
    } else {
      console.error('Interview ID not found in URL');
    }
  };

  const renderStatusIcon = (status: boolean | null) => {
    if (status === true) return <CheckCircle2 className="text-green-500" />;
    if (status === false) return <XCircle className="text-destructive" />;
    return <div className="w-5 h-5 bg-muted-foreground/30 rounded-full animate-pulse"></div>;
  };

  return (
    <div className="page-container py-12">
        <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
                <h1 className="text-4xl font-bold text-foreground">Hardware Check</h1>
                <p className="text-lg text-muted-foreground mt-2">
                    Let's make sure your camera and microphone are ready.
                </p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Camera & Microphone Setup</CardTitle>
                    <CardDescription>Your browser will ask for permission to access your camera and microphone. Please allow it to proceed.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Video Preview */}
                    <div className="bg-muted/50 rounded-lg overflow-hidden aspect-video relative flex items-center justify-center border">
                        <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                        {!cameraPermission && (
                            <div className="absolute flex flex-col items-center text-muted-foreground">
                                <Video size={48} className="mb-2" />
                                <p>Camera Preview</p>
                            </div>
                        )}
                    </div>

                    {/* Permission Status */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                            <div className="flex items-center font-medium">
                                <Video className="mr-3" size={20} /> Camera Access
                            </div>
                            {renderStatusIcon(cameraPermission)}
                        </div>
                        <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                            <div className="flex items-center font-medium">
                                <Mic className="mr-3" size={20} /> Microphone Access
                            </div>
                           {renderStatusIcon(micPermission)}
                        </div>
                    </div>

                    {/* Error Alert */}
                    {error && (
                        <Alert variant="destructive">
                            <AlertTriangle className="h-4 w-4" />
                            <AlertTitle>Permission Error</AlertTitle>
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {/* Action Button */}
                     <Button
                        onClick={handleStartInterview}
                        disabled={!allPermissionsGranted}
                        size="lg"
                        className="w-full"
                    >
                        {allPermissionsGranted ? 'Start Interview' : 'Waiting for Permissions...'}
                    </Button>
                </CardContent>
            </Card>
        </div>
    </div>
  );
};

export default HardwareCheck;
