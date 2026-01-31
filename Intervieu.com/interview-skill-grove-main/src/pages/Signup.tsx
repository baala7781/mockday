import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createUserWithEmailAndPassword, updateProfile, sendEmailVerification, signInWithPopup, GoogleAuthProvider } from "firebase/auth";
import { auth } from '../firebase';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { useToast } from "@/hooks/use-toast";

const SignupPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<'weak' | 'medium' | 'strong' | null>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  const googleProvider = new GoogleAuthProvider();

  const validatePassword = (pwd: string): 'weak' | 'medium' | 'strong' => {
    if (pwd.length < 6) return 'weak';
    if (pwd.length < 10) return 'medium';
    if (pwd.match(/[a-z]/) && pwd.match(/[A-Z]/) && pwd.match(/[0-9]/) && pwd.match(/[^a-zA-Z0-9]/)) {
      return 'strong';
    }
    return 'medium';
  };

  const handlePasswordChange = (pwd: string) => {
    setPassword(pwd);
    if (pwd.length > 0) {
      setPasswordStrength(validatePassword(pwd));
    } else {
      setPasswordStrength(null);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!email || !password || !confirmPassword) {
      setError('Please fill in all required fields');
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords don't match. Please try again.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setIsLoading(true);
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      
      // Update display name if provided
      if (displayName.trim()) {
        await updateProfile(userCredential.user, {
          displayName: displayName.trim()
        });
      }

      // Send email verification
      try {
        await sendEmailVerification(userCredential.user, {
          url: window.location.origin + '/verify-email',
          handleCodeInApp: false, // Open link in browser, not app
        });
        console.log("✅ Verification email sent successfully");
        toast({
          title: "Account created successfully!",
          description: "Please check your email to verify your account before continuing.",
        });
        navigate("/verify-email");
      } catch (verificationError: any) {
        // If email verification fails, still allow signup but show warning
        console.error("❌ Failed to send verification email:", verificationError);
        console.error("Error code:", verificationError.code);
        console.error("Error message:", verificationError.message);
        toast({
          title: "Account created successfully!",
          description: `Email verification failed: ${verificationError.message || 'Please check Firebase Console settings'}`,
          variant: "default",
        });
        navigate("/dashboard");
      }
    } catch (error: any) {
      let errorMessage = "An error occurred while creating your account. Please try again.";
      
      if (error.code === 'auth/email-already-in-use') {
        errorMessage = "An account with this email already exists. Please sign in instead.";
      } else if (error.code === 'auth/invalid-email') {
        errorMessage = "Invalid email address format.";
      } else if (error.code === 'auth/weak-password') {
        errorMessage = "Password is too weak. Please choose a stronger password.";
      } else if (error.code === 'auth/operation-not-allowed') {
        errorMessage = "Email/password accounts are not enabled. Please contact support.";
      }
      
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Sign Up Failed",
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getPasswordStrengthColor = () => {
    if (passwordStrength === 'weak') return 'bg-destructive';
    if (passwordStrength === 'medium') return 'bg-yellow-500';
    if (passwordStrength === 'strong') return 'bg-green-500';
    return 'bg-muted';
  };

  const getPasswordStrengthText = () => {
    if (passwordStrength === 'weak') return 'Weak';
    if (passwordStrength === 'medium') return 'Medium';
    if (passwordStrength === 'strong') return 'Strong';
    return '';
  };

  const handleGoogleSignup = async () => {
    setError(null);
    setIsGoogleLoading(true);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const user = result.user;
      
      toast({
        title: "Account created successfully!",
        description: "Welcome! You've been signed up with Google.",
      });
      navigate("/dashboard");
    } catch (error: any) {
      let errorMessage = "An error occurred during Google signup. Please try again.";
      
      if (error.code === 'auth/account-exists-with-different-credential') {
        errorMessage = "An account with this email already exists. Please sign in instead.";
      } else if (error.code === 'auth/popup-closed-by-user') {
        errorMessage = "Sign-up popup was closed. Please try again.";
      } else if (error.code === 'auth/popup-blocked') {
        errorMessage = "Popup was blocked by your browser. Please allow popups and try again.";
      }
      
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Google Sign Up Failed",
        description: errorMessage,
      });
    } finally {
      setIsGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2 mb-6">
            <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-lg">M</span>
            </div>
            <span className="font-semibold text-2xl text-foreground">MockDay</span>
          </Link>
          <h1 className="text-3xl font-semibold text-foreground mb-2">Create Your Account</h1>
          <p className="text-muted-foreground">Start practicing interviews and improving your skills</p>
        </div>

        <Card className="border-border shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl">Sign Up</CardTitle>
            <CardDescription>
              Enter your information to create your account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSignup} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="displayName">Full Name (Optional)</Label>
                <Input
                  id="displayName"
                  type="text"
                  placeholder="John Doe"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={isLoading}
                  className="h-11"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  required
                  className="h-11"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  disabled={isLoading}
                  required
                  className="h-11"
                />
                {password && passwordStrength && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Password strength:</span>
                      <span className={`font-medium ${
                        passwordStrength === 'weak' ? 'text-destructive' :
                        passwordStrength === 'medium' ? 'text-yellow-600' :
                        'text-green-600'
                      }`}>
                        {getPasswordStrengthText()}
                      </span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-300 ${getPasswordStrengthColor()}`}
                        style={{ 
                          width: passwordStrength === 'weak' ? '33%' : 
                                 passwordStrength === 'medium' ? '66%' : '100%' 
                        }}
                      />
                    </div>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Must be at least 6 characters long
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                  required
                  className="h-11"
                />
                {confirmPassword && password === confirmPassword && confirmPassword.length > 0 && (
                  <div className="flex items-center text-xs text-green-600">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Passwords match
                  </div>
                )}
                {confirmPassword && password !== confirmPassword && (
                  <div className="flex items-center text-xs text-destructive">
                    <AlertCircle className="h-3 w-3 mr-1" />
                    Passwords do not match
                  </div>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11"
                disabled={isLoading || (confirmPassword && password !== confirmPassword)}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </Button>
            </form>

            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    Or continue with
                  </span>
                </div>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full h-11 mt-4"
              onClick={handleGoogleSignup}
              disabled={isLoading || isGoogleLoading}
            >
              {isGoogleLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing up...
                </>
              ) : (
                <>
                  <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  Sign up with Google
                </>
              )}
            </Button>

            <div className="mt-6 text-center text-sm">
              <span className="text-muted-foreground">Already have an account? </span>
              <Link to="/login" className="text-primary font-medium hover:underline">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          By creating an account, you agree to our{" "}
          <Link to="/terms" className="text-primary hover:underline">Terms of Service</Link>
          {" "}and{" "}
          <Link to="/privacy" className="text-primary hover:underline">Privacy Policy</Link>
        </p>
      </div>
    </div>
  );
};

export default SignupPage;
