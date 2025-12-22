import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mail, CheckCircle2, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useToast } from "@/hooks/use-toast";
import { sendEmailVerification, reload, applyActionCode } from "firebase/auth";
import { auth } from '../firebase';
import { getEmailVerificationStatus, verifyEmail } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const VerifyEmailPage: React.FC = () => {
  const { currentUser, loading } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  const [isVerified, setIsVerified] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResendTime, setLastResendTime] = useState<number | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0); // Cooldown in seconds

  // Handle verification link from email (with oobCode) - this works even if user is not logged in
  useEffect(() => {
    const oobCode = searchParams.get('oobCode');
    const mode = searchParams.get('mode');
    
    if (oobCode && mode === 'verifyEmail') {
      handleEmailVerificationLink(oobCode);
    }
  }, [searchParams]);

  const handleEmailVerificationLink = async (oobCode: string) => {
    setIsVerifying(true);
    setError(null);
    try {
      // Apply the verification code - this works even if user is not logged in
      await applyActionCode(auth, oobCode);
      
      // Reload user to get updated verification status (if logged in)
      if (currentUser) {
        await reload(currentUser);
        
        // Update backend
        try {
          const token = await currentUser.getIdToken();
          await verifyEmail(token);
        } catch (e) {
          console.error("Failed to update backend verification status:", e);
        }
      }
      
      setIsVerified(true);
      toast({
        title: "Email Verified!",
        description: "Your email has been successfully verified. You can now log in.",
      });
      
      // Redirect to login after a short delay
      setTimeout(() => {
        navigate("/login");
      }, 2000);
    } catch (err: any) {
      console.error("Error verifying email:", err);
      setError(err.message || "Failed to verify email. The link may have expired.");
      toast({
        variant: "destructive",
        title: "Verification Failed",
        description: err.message || "The verification link may have expired. Please request a new one.",
      });
    } finally {
      setIsVerifying(false);
    }
  };

  // Only redirect to login if there's no oobCode and user is not logged in
  useEffect(() => {
    const oobCode = searchParams.get('oobCode');
    if (!loading && !currentUser && !oobCode) {
      navigate("/login");
    }
  }, [currentUser, loading, navigate, searchParams]);

  const checkVerificationStatus = async () => {
    if (!currentUser) return;
    
    setIsChecking(true);
    setError(null);
    try {
      // Reload user to get latest email verification status from Firebase
      await reload(currentUser);
      
      // Also check backend status
      const token = await currentUser.getIdToken();
      const status = await getEmailVerificationStatus(token);
      
      if (status.emailVerified || currentUser.emailVerified) {
        setIsVerified(true);
        // Update backend
        try {
          await verifyEmail(token);
        } catch (e) {
          console.error("Failed to update backend verification status:", e);
        }
      } else {
        setIsVerified(false);
      }
    } catch (err: any) {
      console.error("Error checking verification status:", err);
      setError("Failed to check verification status. Please try again.");
    } finally {
      setIsChecking(false);
    }
  };

  const handleResendVerification = async () => {
    if (!currentUser) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Please log in to resend verification email.",
      });
      return;
    }
    
    // Check cooldown period (60 seconds)
    const now = Date.now();
    if (lastResendTime && (now - lastResendTime) < 60000) {
      const remaining = Math.ceil((60000 - (now - lastResendTime)) / 1000);
      toast({
        variant: "default",
        title: "Please wait",
        description: `Please wait ${remaining} seconds before requesting another email.`,
      });
      return;
    }
    
    setIsResending(true);
    setError(null);
    try {
      await sendEmailVerification(currentUser, {
        url: window.location.origin + '/verify-email',
        handleCodeInApp: false,
      });
      console.log("✅ Verification email sent successfully");
      setLastResendTime(now);
      setResendCooldown(60); // Start 60 second cooldown
      
      // Countdown timer
      const interval = setInterval(() => {
        setResendCooldown((prev) => {
          if (prev <= 1) {
            clearInterval(interval);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      
      toast({
        title: "Verification email sent!",
        description: "Please check your inbox (and spam folder) and click the verification link.",
      });
    } catch (err: any) {
      console.error("❌ Error sending verification email:", err);
      console.error("Error code:", err.code);
      console.error("Error message:", err.message);
      
      let errorMessage = err.message || 'Unknown error';
      
      // Handle specific Firebase errors
      if (err.code === 'auth/too-many-requests') {
        errorMessage = "Too many requests. Please wait a few minutes before trying again.";
        setResendCooldown(120); // 2 minute cooldown for rate limit
      }
      
      setError(`Failed to send verification email: ${errorMessage}`);
      toast({
        variant: "destructive",
        title: "Error",
        description: `Failed to send verification email: ${errorMessage}`,
      });
    } finally {
      setIsResending(false);
    }
  };

  // Check verification status on mount and periodically
  useEffect(() => {
    if (currentUser) {
      checkVerificationStatus();
      // Check every 5 seconds
      const interval = setInterval(checkVerificationStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [currentUser]);

  if (loading || isVerifying) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">
            {isVerifying ? "Verifying your email..." : "Loading..."}
          </p>
        </div>
      </div>
    );
  }

  // If verifying via link (oobCode), show verification status even if not logged in
  const oobCode = searchParams.get('oobCode');
  const isVerifyingViaLink = oobCode && searchParams.get('mode') === 'verifyEmail';
  
  // If no user and no verification link, redirect to login (handled by useEffect)
  if (!currentUser && !isVerifyingViaLink) {
    return null; // Will redirect via useEffect
  }

  if (isVerified) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 lg:px-8 py-12">
        <div className="w-full max-w-md">
          <Card className="border-border shadow-lg">
            <CardHeader className="text-center">
              <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
              </div>
              <CardTitle className="text-2xl">Email Verified!</CardTitle>
              <CardDescription>
                Your email has been successfully verified.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button 
                className="w-full" 
                onClick={() => navigate("/dashboard")}
              >
                Go to Dashboard
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2 mb-6">
            <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-lg">I</span>
            </div>
            <span className="font-semibold text-2xl text-foreground">MockDay</span>
          </Link>
          <h1 className="text-3xl font-semibold text-foreground mb-2">Verify Your Email</h1>
          <p className="text-muted-foreground">We've sent a verification link to your email</p>
        </div>

        <Card className="border-border shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl">Check Your Email</CardTitle>
            <CardDescription>
              {currentUser ? (
                <>We sent a verification email to <strong>{currentUser.email}</strong></>
              ) : (
                <>Please check your email for the verification link</>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex items-center justify-center p-6 bg-muted rounded-lg">
              <Mail className="h-12 w-12 text-muted-foreground" />
            </div>

            <div className="space-y-2 text-sm text-muted-foreground">
              <p>1. Check your inbox for an email from MockDay</p>
              <p>2. Click the verification link in the email</p>
              <p>3. Come back here and click "I've Verified"</p>
            </div>

            {currentUser ? (
              <>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={handleResendVerification}
                    disabled={isResending || resendCooldown > 0}
                  >
                    {isResending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : resendCooldown > 0 ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Resend ({resendCooldown}s)
                      </>
                    ) : (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Resend Email
                      </>
                    )}
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={checkVerificationStatus}
                    disabled={isChecking}
                  >
                    {isChecking ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Checking...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="mr-2 h-4 w-4" />
                        I've Verified
                      </>
                    )}
                  </Button>
                </div>

                <div className="pt-4 border-t">
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => navigate("/dashboard")}
                  >
                    Skip for now (verify later)
                  </Button>
                </div>
              </>
            ) : (
              <div className="pt-4">
                <Button
                  className="w-full"
                  onClick={() => navigate("/login")}
                >
                  Go to Login
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default VerifyEmailPage;

