import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { getEmailVerificationStatus } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mail, Loader2, AlertCircle } from 'lucide-react';
import { reload } from "firebase/auth";

interface EmailVerificationGuardProps {
  children: React.ReactNode;
  redirectTo?: string;
  showWarning?: boolean; // If true, show warning but allow access
}

const EmailVerificationGuard: React.FC<EmailVerificationGuardProps> = ({ 
  children, 
  redirectTo = "/verify-email",
  showWarning = false 
}) => {
  const { currentUser, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [isVerified, setIsVerified] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkVerification = async () => {
      if (!currentUser) {
        setIsChecking(false);
        return;
      }

      try {
        // Reload user to get latest email verification status
        await reload(currentUser);
        
        // Check backend status
        const token = await currentUser.getIdToken();
        const status = await getEmailVerificationStatus(token);
        
        setIsVerified(status.emailVerified || currentUser.emailVerified || false);
      } catch (error) {
        console.error("Error checking email verification:", error);
        // On error, assume not verified to be safe
        setIsVerified(false);
      } finally {
        setIsChecking(false);
      }
    };

    if (!authLoading && currentUser) {
      checkVerification();
    } else if (!authLoading && !currentUser) {
      setIsChecking(false);
    }
  }, [currentUser, authLoading]);

  if (authLoading || isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!currentUser) {
    return <>{children}</>;
  }

  // If not verified and showWarning is false, redirect to verification page
  if (!isVerified && !showWarning) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center gap-3 mb-2">
              <Mail className="h-6 w-6 text-muted-foreground" />
              <CardTitle>Email Verification Required</CardTitle>
            </div>
            <CardDescription>
              Please verify your email address to access this feature.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                We've sent a verification email to <strong>{currentUser.email}</strong>. 
                Please check your inbox and verify your email to continue.
              </AlertDescription>
            </Alert>
            <Button 
              className="w-full" 
              onClick={() => navigate(redirectTo)}
            >
              Go to Verification Page
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If not verified but showWarning is true, show warning banner but allow access
  if (!isVerified && showWarning) {
    return (
      <div className="space-y-4">
        <Alert variant="default" className="bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800">
          <Mail className="h-4 w-4" />
          <AlertDescription>
            <div className="flex items-center justify-between">
              <span>
                Please verify your email address to access all features. 
                <Button 
                  variant="link" 
                  className="p-0 h-auto ml-1 text-yellow-700 dark:text-yellow-400"
                  onClick={() => navigate(redirectTo)}
                >
                  Verify now
                </Button>
              </span>
            </div>
          </AlertDescription>
        </Alert>
        {children}
      </div>
    );
  }

  // Email is verified, allow access
  return <>{children}</>;
};

export default EmailVerificationGuard;


