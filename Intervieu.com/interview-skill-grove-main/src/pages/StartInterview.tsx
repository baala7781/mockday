import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText, AlertTriangle, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
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

const StartInterview: React.FC = () => {
  const [selectedRole, setSelectedRole] = useState<InterviewRole>('software-engineer');
  const [selectedResumeId, setSelectedResumeId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { currentUser, resumes, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleProceed = async () => {
    if (!currentUser) {
      setError('You must be logged in to start an interview.');
      return;
    }

    // Validate resume selection - must select from existing resumes
    if (!selectedResumeId) {
      if (resumes.length === 0) {
        setError('Please upload a resume in your profile first.');
        toast({
          variant: "destructive",
          title: "No Resume",
          description: "Please upload a resume in your profile before starting an interview.",
        });
        return;
      }
      setError('Please select a resume from your uploaded resumes.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (!currentUser) {
        throw new Error('User not authenticated');
      }

      // Use selected resume (already parsed and stored)
      const resumeId = selectedResumeId;

      // Map role to backend format
      const backendRole = mapRoleToBackend(selectedRole);

      // Start interview via API
      const response = await interviewService.startInterview({
        user_id: currentUser.uid,
        role: backendRole,
        resume_id: resumeId,
      });

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
            <CardContent>
              <Select 
                value={selectedRole} 
                onValueChange={(value) => setSelectedRole(value as InterviewRole)}
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
                  <SelectItem value="data-science">
                    <div className="flex items-center gap-2">
                      <span>Data Science</span>
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
                  <SelectItem value="graduate-data-engineer">
                    <div className="flex items-center gap-2">
                      <span>Graduate Data Engineer</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="graduate-data-scientist">
                    <div className="flex items-center gap-2">
                      <span>Graduate Data Scientist</span>
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
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Resume Selection Card */}
          <Card className="border-border shadow-sm">
            <CardHeader>
              <CardTitle>Resume Selection</CardTitle>
              <CardDescription>
                Select a resume from your profile (resumes are parsed when uploaded)
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
                      No resumes uploaded yet. Please upload one in your profile first.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate('/profile/setup')}
                    >
                      Go to Profile
                    </Button>
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
              disabled={isLoading || !selectedResumeId || resumes.length === 0}
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
