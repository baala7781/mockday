import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText, AlertTriangle, CheckCircle2, Loader2, Sparkles, Key, Eye, EyeOff } from 'lucide-react';
import { Alert, AlertDescription } from "@/components/ui/alert";
import { InterviewRole } from '@/lib/types';
import { useToast } from "@/hooks/use-toast";
import { interviewService } from '@/services/interviewService';

// Map frontend role to backend role
const mapRoleToBackend = (role: InterviewRole): string => {
  const roleMap: Record<InterviewRole, string> = {
    'software-engineer': 'fullstack-developer',
    'frontend-developer': 'frontend-developer',
    'backend-developer': 'backend-developer',
    'fullstack-developer': 'fullstack-developer',
    'data-scientist': 'data-scientist',
    'data-science': 'data-science',
    'data-engineer': 'data-engineer',
    'graduate': 'graduate',
    'graduate-data-engineer': 'graduate-data-engineer',
    'graduate-data-scientist': 'graduate-data-scientist',
    'devops-engineer': 'devops-engineer',
    'machine-learning-engineer': 'machine-learning-engineer',
    'cloud-engineer': 'cloud-engineer',
    'security-engineer': 'security-engineer',
    'product-manager': 'fullstack-developer', // Default mapping
  };
  return roleMap[role] || 'fullstack-developer';
};

// Control whether users can choose between BYOK and system API
// If true: Show checkbox, user can choose
// If false: Force BYOK only (no checkbox, users must use their own keys)
const BYOK_OPTION_ENABLED = import.meta.env.VITE_ENABLE_BYOK_OPTION !== 'false'; // Default to true if not set

// Debug: Log the env variable value (remove in production if needed)
if (import.meta.env.DEV) {
  console.log('🔧 BYOK_OPTION_ENABLED:', BYOK_OPTION_ENABLED);
  console.log('🔧 VITE_ENABLE_BYOK_OPTION env value:', import.meta.env.VITE_ENABLE_BYOK_OPTION);
}

// Validate API key formats (defined outside component to avoid recreation)
const validateDeepgramKey = (key: string): string | null => {
  if (!key.trim()) return null; // Empty is handled by required validation
  // Deepgram keys should NOT start with "sk-" (that's OpenRouter format)
  if (key.trim().startsWith('sk-')) {
    return 'This looks like an OpenRouter API key. Please use your Deepgram API key instead.';
  }
  return null;
};

const validateOpenRouterKey = (key: string): string | null => {
  if (!key.trim()) return null; // Empty is handled by required validation
  // OpenRouter keys should start with "sk-"
  if (!key.trim().startsWith('sk-')) {
    return 'OpenRouter API keys should start with "sk-". Please check your key.';
  }
  return null;
};

const StartInterview: React.FC = () => {
  const [selectedRole, setSelectedRole] = useState<InterviewRole | 'custom'>('software-engineer');
  const [customRole, setCustomRole] = useState<string>('');
  const [selectedResumeId, setSelectedResumeId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { currentUser, resumes, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  // BYOK state
  // If BYOK_OPTION_ENABLED is false, always use BYOK (useBYOK is always true)
  const [useBYOK, setUseBYOK] = useState(!BYOK_OPTION_ENABLED); // Force true if option disabled
  const [deepgramKey, setDeepgramKey] = useState('');
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [showDeepgramKey, setShowDeepgramKey] = useState(false);
  const [showOpenrouterKey, setShowOpenrouterKey] = useState(false);
  const [deepgramKeyError, setDeepgramKeyError] = useState<string | null>(null);
  const [openrouterKeyError, setOpenrouterKeyError] = useState<string | null>(null);
  
  // Load saved BYOK keys from localStorage on mount
  useEffect(() => {
    const savedDeepgram = localStorage.getItem('byok_deepgram_key');
    const savedOpenrouter = localStorage.getItem('byok_openrouter_key');
    if (savedDeepgram) {
      setDeepgramKey(savedDeepgram);
      // Validate loaded key
      const error = validateDeepgramKey(savedDeepgram);
      setDeepgramKeyError(error);
      if (BYOK_OPTION_ENABLED) {
        setUseBYOK(true);
      }
    }
    if (savedOpenrouter) {
      setOpenrouterKey(savedOpenrouter);
      // Validate loaded key
      const error = validateOpenRouterKey(savedOpenrouter);
      setOpenrouterKeyError(error);
      if (BYOK_OPTION_ENABLED) {
        setUseBYOK(true);
      }
    }
  }, []);

  // Auto-select resume if only one exists
  useEffect(() => {
    if (resumes.length === 1 && !selectedResumeId) {
      setSelectedResumeId(resumes[0].id);
    }
  }, [resumes, selectedResumeId]);

  const handleProceed = async () => {
    if (!currentUser) {
      setError('You must be logged in to start an interview.');
      return;
    }

    // Validate resume selection - show warning if resumes exist but none selected
    if (!selectedResumeId && resumes.length > 0) {
      setError('Please select a resume to start the interview.');
      toast({
        variant: "destructive",
        title: "Resume Required",
        description: "Please select a resume from your uploaded resumes to start the interview.",
      });
      return;
    }

    // If no resumes, allow proceeding with profile data (students without resumes)
    // The backend will use profile data (skills, experience, education) from the user's profile

    setIsLoading(true);
    setError(null);

    try {
      if (!currentUser) {
        throw new Error('User not authenticated');
      }

      // Use selected resume (already parsed and stored)
      const resumeId = selectedResumeId;

      // Map role to backend format (use custom role if selected)
      const backendRole = selectedRole === 'custom' 
        ? customRole.trim() 
        : mapRoleToBackend(selectedRole as InterviewRole);
      
      if (!backendRole || backendRole.trim() === '') {
        setError('Please select a role or enter a custom role.');
        setIsLoading(false);
        return;
      }

      // Validate BYOK keys if BYOK is required or enabled
      if (useBYOK || !BYOK_OPTION_ENABLED) {
        if (!deepgramKey.trim()) {
          setError('Deepgram API key is required.');
          setIsLoading(false);
          return;
        }
        if (!openrouterKey.trim()) {
          setError('OpenRouter API key is required.');
          setIsLoading(false);
          return;
        }

        // Validate API key formats
        const deepgramError = validateDeepgramKey(deepgramKey);
        const openrouterError = validateOpenRouterKey(openrouterKey);
        
        if (deepgramError) {
          setDeepgramKeyError(deepgramError);
          setError(deepgramError);
          setIsLoading(false);
          return;
        }
        
        if (openrouterError) {
          setOpenrouterKeyError(openrouterError);
          setError(openrouterError);
          setIsLoading(false);
          return;
        }
      }

      // Save BYOK keys to localStorage if provided
      if (useBYOK || !BYOK_OPTION_ENABLED) {
        if (deepgramKey.trim()) {
          localStorage.setItem('byok_deepgram_key', deepgramKey.trim());
        } else {
          localStorage.removeItem('byok_deepgram_key');
        }
        if (openrouterKey.trim()) {
          localStorage.setItem('byok_openrouter_key', openrouterKey.trim());
        } else {
          localStorage.removeItem('byok_openrouter_key');
        }
      }

      // Start interview via API
      const requestParams: any = {
        user_id: currentUser.uid,
        role: backendRole,
      };
      
      // Only include resume_id if a resume is selected
      if (selectedResumeId) {
        requestParams.resume_id = selectedResumeId;
      }
      
      // Add BYOK OpenRouter key if BYOK is enabled or required
      if ((useBYOK || !BYOK_OPTION_ENABLED) && openrouterKey.trim()) {
        requestParams.byok_openrouter_key = openrouterKey.trim();
      }
      
      const response = await interviewService.startInterview(requestParams);

      console.log('Interview started:', response);

      // Navigate to hardware check, then to interview
      navigate(`/hardware-check?interviewId=${response.interview_id}`);
      setIsLoading(false);

    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
      setIsLoading(false);
      toast({
        variant: "destructive",
        title: "Error",
        description: err.message || 'An unexpected error occurred.',
      });
    }
  };

  return (
    <div className="page-container py-12">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <Sparkles className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-4xl font-bold text-foreground mb-2">Start Your Mock Interview</h1>
          <p className="text-lg text-muted-foreground">
            Select your role and resume to begin a personalized interview experience
          </p>
        </div>

        <div className="space-y-6">
          {/* Role Selection Card */}
          <Card className="border-border shadow-sm">
            <CardHeader>
              <CardTitle>Select Interview Role</CardTitle>
              <CardDescription>Choose the role you want to practice for</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select 
                value={selectedRole} 
                onValueChange={(value) => {
                  setSelectedRole(value as InterviewRole | 'custom');
                  if (value !== 'custom') {
                    setCustomRole(''); // Clear custom role when selecting predefined
                  }
                }}
              >
                <SelectTrigger className="w-full h-12">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="software-engineer">
                    <div className="flex items-center gap-2">
                      <span>Software Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="frontend-developer">
                    <div className="flex items-center gap-2">
                      <span>Frontend Developer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="backend-developer">
                    <div className="flex items-center gap-2">
                      <span>Backend Developer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="fullstack-developer">
                    <div className="flex items-center gap-2">
                      <span>Full Stack Developer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="data-scientist">
                    <div className="flex items-center gap-2">
                      <span>Data Scientist</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="data-engineer">
                    <div className="flex items-center gap-2">
                      <span>Data Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="graduate">
                    <div className="flex items-center gap-2">
                      <span>Graduate</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="devops-engineer">
                    <div className="flex items-center gap-2">
                      <span>DevOps Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="machine-learning-engineer">
                    <div className="flex items-center gap-2">
                      <span>Machine Learning Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="cloud-engineer">
                    <div className="flex items-center gap-2">
                      <span>Cloud Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="security-engineer">
                    <div className="flex items-center gap-2">
                      <span>Security Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="product-manager">
                    <div className="flex items-center gap-2">
                      <span>Product Manager</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="custom">
                    <div className="flex items-center gap-2">
                      <span>Custom Role (Type your own)</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
              
              {selectedRole === 'custom' && (
                <div className="space-y-2">
                  <Label htmlFor="custom-role">Enter Custom Role</Label>
                  <Input
                    id="custom-role"
                    value={customRole}
                    onChange={(e) => setCustomRole(e.target.value)}
                    placeholder="e.g., QA Engineer, Technical Writer, Solutions Architect"
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter the role you want to practice for
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Resume Selection Card */}
          <Card className="border-border shadow-sm">
            <CardHeader>
              <CardTitle>Resume Selection {resumes.length === 0 && '(Optional)'}</CardTitle>
              <CardDescription>
                {resumes.length > 0 
                  ? 'Select a resume from your profile (resumes are parsed when uploaded)'
                  : 'Students without resumes can start an interview using profile details (skills, experience, education) from their profile'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="font-medium">Select Resume</div>
                {resumes.length > 0 ? (
                  <div className="space-y-2">
                    {resumes.map((resume) => (
                      <div
                        key={resume.id}
                        onClick={() => setSelectedResumeId(resume.id)}
                        className={`p-3 border-2 rounded-lg cursor-pointer transition-all ${
                          selectedResumeId === resume.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <FileText className="h-5 w-5 text-primary" />
                            <div>
                              <p className="text-sm font-medium">{resume.name}</p>
                              <p className="text-xs text-muted-foreground">
                                Uploaded {new Date(resume.uploadedAt || Date.now()).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                          {selectedResumeId === resume.id && (
                            <CheckCircle2 className="h-5 w-5 text-primary" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 border border-dashed border-border rounded-lg text-center bg-muted/30">
                    <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground opacity-50" />
                    <p className="text-sm text-muted-foreground mb-3">
                      No resumes uploaded. You can start an interview using your profile details (skills, experience, education) or upload a resume in your profile.
                    </p>
                    <div className="flex gap-2 justify-center">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate('/profile/setup')}
                      >
                        Go to Profile
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* BYOK Section */}
          <Card className="border-border shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                {BYOK_OPTION_ENABLED ? 'API Keys (Optional)' : 'API Keys (Required)'}
              </CardTitle>
              <CardDescription>
                {BYOK_OPTION_ENABLED 
                  ? 'Optional: Use your own API keys for Deepgram and OpenRouter. Keys are stored locally in your browser only.'
                  : 'You must provide your own API keys for Deepgram and OpenRouter. Keys are stored locally in your browser only.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {BYOK_OPTION_ENABLED && (
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="use-byok"
                    checked={useBYOK}
                    onChange={(e) => setUseBYOK(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <Label htmlFor="use-byok" className="cursor-pointer">
                    Use my own API keys
                  </Label>
                </div>
              )}
              
              {(useBYOK || !BYOK_OPTION_ENABLED) && (
                <div className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <Label htmlFor="deepgram-key">Deepgram API Key {!BYOK_OPTION_ENABLED && <span className="text-destructive">*</span>}</Label>
                    <div className="relative">
                      <Input
                        id="deepgram-key"
                        type={showDeepgramKey ? "text" : "password"}
                        placeholder="Enter your Deepgram API key"
                        value={deepgramKey}
                        onChange={(e) => {
                          const value = e.target.value;
                          setDeepgramKey(value);
                          // Real-time validation
                          const error = validateDeepgramKey(value);
                          setDeepgramKeyError(error);
                          if (error) {
                            setError(error);
                          } else if (error === null && deepgramKeyError) {
                            setError(null);
                          }
                        }}
                        className={`pr-10 ${deepgramKeyError ? 'border-destructive' : ''}`}
                        required={!BYOK_OPTION_ENABLED}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                        onClick={() => setShowDeepgramKey(!showDeepgramKey)}
                      >
                        {showDeepgramKey ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                    {deepgramKeyError && (
                      <p className="text-xs text-destructive flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" />
                        {deepgramKeyError}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Get your key from{' '}
                      <a
                        href="https://console.deepgram.com/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Deepgram Console
                      </a>
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="openrouter-key">OpenRouter API Key {!BYOK_OPTION_ENABLED && <span className="text-destructive">*</span>}</Label>
                    <div className="relative">
                      <Input
                        id="openrouter-key"
                        type={showOpenrouterKey ? "text" : "password"}
                        placeholder="Enter your OpenRouter API key (should start with sk-)"
                        value={openrouterKey}
                        onChange={(e) => {
                          const value = e.target.value;
                          setOpenrouterKey(value);
                          // Real-time validation
                          const error = validateOpenRouterKey(value);
                          setOpenrouterKeyError(error);
                          if (error) {
                            setError(error);
                          } else if (error === null && openrouterKeyError) {
                            setError(null);
                          }
                        }}
                        className={`pr-10 ${openrouterKeyError ? 'border-destructive' : ''}`}
                        required={!BYOK_OPTION_ENABLED}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                        onClick={() => setShowOpenrouterKey(!showOpenrouterKey)}
                      >
                        {showOpenrouterKey ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                    {openrouterKeyError && (
                      <p className="text-xs text-destructive flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" />
                        {openrouterKeyError}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Get your key from{' '}
                      <a
                        href="https://openrouter.ai/keys"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        OpenRouter
                      </a>
                      {' '}(keys start with "sk-")
                    </p>
                  </div>
                  
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription className="text-xs">
                      Your API keys are stored locally in your browser only. They are never sent to our servers.
                      Clear your browser data to remove saved keys.
                    </AlertDescription>
                  </Alert>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4">
            <Button
              variant="outline"
              onClick={() => navigate('/dashboard')}
              disabled={isLoading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleProceed}
              disabled={
                isLoading || 
                (resumes.length > 0 && !selectedResumeId) || 
                ((useBYOK || !BYOK_OPTION_ENABLED) && (!deepgramKey.trim() || !openrouterKey.trim())) ||
                !!deepgramKeyError ||
                !!openrouterKeyError
              }
              size="lg"
              className="flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting Interview...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Start Interview
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StartInterview;
