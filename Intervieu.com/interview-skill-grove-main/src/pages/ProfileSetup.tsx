import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { UploadCloud, FileText, Plus, CheckCircle2, Loader2, MapPin, Briefcase, GraduationCap, Linkedin, AlertCircle, Trash2 } from 'lucide-react';
import { useToast } from "@/hooks/use-toast";
import { updateProfile, uploadResume, deleteResume } from '@/lib/api';

interface ExperienceItem {
  role: string;
  company: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
  description: string;
}

interface EducationItem {
  degree: string;
  institution: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
}

const ProfileSetup: React.FC = () => {
  const { currentUser, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  // Basic Info
  const [fullName, setFullName] = useState(currentUser?.displayName || '');
  const [location, setLocation] = useState('');
  const [experienceLevel, setExperienceLevel] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [bio, setBio] = useState('');
  
  // Resume
  const [resumes, setResumes] = useState<Array<{ id: string; name: string; uploadedAt: string }>>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string>('');
  const [uploadingResume, setUploadingResume] = useState(false);
  
  // Experience
  const [experiences, setExperiences] = useState<ExperienceItem[]>([]);
  const [showExperienceForm, setShowExperienceForm] = useState(false);
  const [newExperience, setNewExperience] = useState<ExperienceItem>({
    role: '',
    company: '',
    location: '',
    startDate: '',
    endDate: '',
    current: false,
    description: ''
  });
  
  // Education
  const [educations, setEducations] = useState<EducationItem[]>([]);
  const [showEducationForm, setShowEducationForm] = useState(false);
  const [newEducation, setNewEducation] = useState<EducationItem>({
    degree: '',
    institution: '',
    location: '',
    startDate: '',
    endDate: '',
    current: false
  });
  
  // Skills
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);

  // Use cached data from AuthContext - no API calls needed
  const { profile: profileData, resumes: resumesData } = useAuth();

  useEffect(() => {
    // Load profile and resumes from cached AuthContext data
    if (profileData) {
      setFullName(profileData.name || currentUser?.displayName || '');
      setLocation(profileData.location || '');
      setExperienceLevel(profileData.experienceLevel || '');
      setLinkedinUrl(profileData.linkedinUrl || '');
      setBio(profileData.bio || '');
      setSkills(profileData.skills || []);
      // Load experiences and educations from profile data
      setExperiences(profileData.experiences || []);
      setEducations(profileData.educations || []);
    }
    if (resumesData) {
      setResumes(resumesData.map(r => ({ 
        id: r.id, 
        name: r.name, 
        uploadedAt: r.uploadedAt || new Date().toISOString() 
      })));
    }
  }, [profileData, resumesData, currentUser]);

  const handleAddExperience = () => {
    if (!newExperience.role || !newExperience.company || !newExperience.startDate) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please fill in role, company, and start date.",
      });
      return;
    }
    setExperiences([...experiences, { ...newExperience }]);
    setNewExperience({
      role: '',
      company: '',
      location: '',
      startDate: '',
      endDate: '',
      current: false,
      description: ''
    });
    setShowExperienceForm(false);
  };

  const handleRemoveExperience = (index: number) => {
    setExperiences(experiences.filter((_, i) => i !== index));
  };

  const handleAddEducation = () => {
    if (!newEducation.degree || !newEducation.institution || !newEducation.startDate) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please fill in degree, institution, and start date.",
      });
      return;
    }
    setEducations([...educations, { ...newEducation }]);
    setNewEducation({
      degree: '',
      institution: '',
      location: '',
      startDate: '',
      endDate: '',
      current: false
    });
    setShowEducationForm(false);
  };

  const handleRemoveEducation = (index: number) => {
    setEducations(educations.filter((_, i) => i !== index));
  };

  const handleAddSkill = () => {
    if (skillInput.trim() && !skills.includes(skillInput.trim())) {
      setSkills([...skills, skillInput.trim()]);
      setSkillInput('');
    }
  };

  const handleRemoveSkill = (skill: string) => {
    setSkills(skills.filter(s => s !== skill));
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      toast({
        variant: "destructive",
        title: "File Too Large",
        description: "Resume must be less than 5MB.",
      });
      return;
    }

    try {
      setUploadingResume(true);
      if (!currentUser) return;
      const token = await currentUser.getIdToken();
      
      // Upload file and parse immediately
      const result = await uploadResume(token, file);
      
      // Refresh global profile/resumes state (this will update AuthContext)
      await refreshProfile();
      
      // Update local state from refreshed AuthContext data
      // The useEffect will handle this automatically, but we can also set it directly
      setSelectedResumeId(result.resume.id);
      
      toast({ 
        title: "Resume Uploaded & Parsed", 
        description: `Resume parsed successfully. Found ${result.resume.skills.length} skills and ${result.resume.projects.length} projects.` 
      });
    } catch (err: any) {
      toast({ variant: 'destructive', title: 'Upload Failed', description: err.message || 'Please try again.' });
    } finally {
      setUploadingResume(false);
    }
  };

  const handleDeleteResume = async (resumeId: string) => {
    if (!confirm('Are you sure you want to delete this resume? This action cannot be undone.')) {
      return;
    }

    try {
      if (!currentUser) return;
      const token = await currentUser.getIdToken();
      await deleteResume(token, resumeId);
      
      // Refresh global profile/resumes state
      await refreshProfile();
      
      // Clear selected resume if it was deleted
      if (selectedResumeId === resumeId) {
        setSelectedResumeId('');
      }
      
      toast({ 
        title: "Resume Deleted", 
        description: "Resume has been deleted successfully." 
      });
    } catch (err: any) {
      toast({ variant: 'destructive', title: 'Delete Failed', description: err.message || 'Please try again.' });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!fullName || !experienceLevel) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please fill in all required fields.",
      });
      return;
    }

    try {
      setIsLoading(true);
      if (!currentUser) throw new Error('Not authenticated');
      const token = await currentUser.getIdToken();
      await updateProfile(token, {
        name: fullName,
        location,
        experienceLevel,
        linkedinUrl,
        bio,
        experiences,
        educations,
        skills,
      });
      
      // Refresh profile data to get updated data from backend
      await refreshProfile();
      
      toast({ title: 'Profile Saved!', description: 'Your profile has been updated successfully.' });
      // Don't navigate away - let user see the saved data
    } catch (err: any) {
      toast({ variant: 'destructive', title: 'Save Failed', description: err.message || 'Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="page-container py-12">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-2">Complete Your Profile</h1>
          <p className="text-lg text-muted-foreground">
            Set up your profile to get personalized interview experiences
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Tell us about yourself</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="fullName">Full Name *</Label>
                  <Input
                    id="fullName"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="John Doe"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="location">Location</Label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="location"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="San Francisco, CA"
                      className="pl-10"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="experienceLevel">Experience Level *</Label>
                  <Select value={experienceLevel} onValueChange={setExperienceLevel} required>
                    <SelectTrigger id="experienceLevel">
                      <SelectValue placeholder="Select experience level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="entry">Entry Level (0-2 years)</SelectItem>
                      <SelectItem value="mid">Mid-Level (3-5 years)</SelectItem>
                      <SelectItem value="senior">Senior (6-10 years)</SelectItem>
                      <SelectItem value="executive">Executive (10+ years)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="linkedin">LinkedIn URL</Label>
                  <div className="relative">
                    <Linkedin className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="linkedin"
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      placeholder="linkedin.com/in/yourprofile"
                      className="pl-10"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="bio">Bio</Label>
                <Textarea
                  id="bio"
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  placeholder="Tell us about yourself, your career goals, and what you're looking for..."
                  rows={4}
                />
              </div>
            </CardContent>
          </Card>

          {/* Resume Section */}
          <Card>
            <CardHeader>
              <CardTitle>Resume</CardTitle>
              <CardDescription>Upload your resume or select from existing ones</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {resumes.length > 0 && (
                <div className="space-y-2">
                  <Label>Select Existing Resume</Label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {resumes.map((resume) => (
                      <div
                        key={resume.id}
                        className={`p-4 border-2 rounded-lg transition-all ${
                          selectedResumeId === resume.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div 
                            className="flex items-center space-x-3 flex-1 cursor-pointer"
                            onClick={() => setSelectedResumeId(resume.id)}
                          >
                            <FileText className="h-5 w-5 text-primary" />
                            <div>
                              <p className="font-medium text-sm">{resume.name}</p>
                              <p className="text-xs text-muted-foreground">
                                {new Date(resume.uploadedAt).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {selectedResumeId === resume.id && (
                              <CheckCircle2 className="h-5 w-5 text-primary" />
                            )}
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteResume(resume.id);
                              }}
                              className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>Or Upload New Resume</Label>
                <div className="relative border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary transition-colors">
                  <input
                    type="file"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    onChange={handleResumeUpload}
                    accept=".pdf,.doc,.docx,.txt"
                    disabled={uploadingResume}
                  />
                  <div className="flex flex-col items-center justify-center">
                    {uploadingResume ? (
                      <>
                        <Loader2 className="h-10 w-10 mb-3 text-primary animate-spin" />
                        <p className="text-sm text-muted-foreground">Uploading...</p>
                      </>
                    ) : (
                      <>
                        <UploadCloud size={40} className="mb-3 text-muted-foreground" />
                        <p className="text-sm font-medium text-foreground mb-1">
                          Click or drag to upload
                        </p>
                        <p className="text-xs text-muted-foreground">
                          PDF, DOC, DOCX, or TXT (Max 5MB)
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Experience Section */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Work Experience</CardTitle>
                  <CardDescription>Add your professional experience</CardDescription>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowExperienceForm(!showExperienceForm)}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Experience
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {showExperienceForm && (
                <div className="p-4 border border-border rounded-lg space-y-4 bg-muted/30">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Role *</Label>
                      <Input
                        value={newExperience.role}
                        onChange={(e) => setNewExperience({ ...newExperience, role: e.target.value })}
                        placeholder="Software Engineer"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Company *</Label>
                      <Input
                        value={newExperience.company}
                        onChange={(e) => setNewExperience({ ...newExperience, company: e.target.value })}
                        placeholder="Tech Corp"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>Location</Label>
                      <Input
                        value={newExperience.location}
                        onChange={(e) => setNewExperience({ ...newExperience, location: e.target.value })}
                        placeholder="San Francisco, CA"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Start Date *</Label>
                      <Input
                        type="month"
                        value={newExperience.startDate}
                        onChange={(e) => setNewExperience({ ...newExperience, startDate: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Date</Label>
                      <Input
                        type="month"
                        value={newExperience.endDate}
                        onChange={(e) => setNewExperience({ ...newExperience, endDate: e.target.value })}
                        disabled={newExperience.current}
                      />
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id="current-exp"
                          checked={newExperience.current}
                          onChange={(e) => setNewExperience({ ...newExperience, current: e.target.checked, endDate: '' })}
                          className="rounded"
                        />
                        <Label htmlFor="current-exp" className="text-xs">Current Position</Label>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Description</Label>
                    <Textarea
                      value={newExperience.description}
                      onChange={(e) => setNewExperience({ ...newExperience, description: e.target.value })}
                      placeholder="Describe your role and achievements..."
                      rows={3}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button type="button" onClick={handleAddExperience}>Add</Button>
                    <Button type="button" variant="outline" onClick={() => setShowExperienceForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {experiences.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Briefcase className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No experience added yet</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {experiences.map((exp, index) => (
                    <div key={index} className="p-4 border border-border rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-semibold">{exp.role}</h4>
                          <p className="text-sm text-muted-foreground">{exp.company}</p>
                          {exp.location && (
                            <p className="text-xs text-muted-foreground">{exp.location}</p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(exp.startDate).toLocaleDateString()} -{' '}
                            {exp.current ? 'Present' : new Date(exp.endDate).toLocaleDateString()}
                          </p>
                          {exp.description && (
                            <p className="text-sm mt-2 text-foreground/80">{exp.description}</p>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveExperience(index)}
                        >
                          ×
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Education Section */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Education</CardTitle>
                  <CardDescription>Add your educational background</CardDescription>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowEducationForm(!showEducationForm)}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Education
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {showEducationForm && (
                <div className="p-4 border border-border rounded-lg space-y-4 bg-muted/30">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Degree *</Label>
                      <Input
                        value={newEducation.degree}
                        onChange={(e) => setNewEducation({ ...newEducation, degree: e.target.value })}
                        placeholder="Bachelor of Science in Computer Science"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Institution *</Label>
                      <Input
                        value={newEducation.institution}
                        onChange={(e) => setNewEducation({ ...newEducation, institution: e.target.value })}
                        placeholder="University Name"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>Location</Label>
                      <Input
                        value={newEducation.location}
                        onChange={(e) => setNewEducation({ ...newEducation, location: e.target.value })}
                        placeholder="City, Country"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Start Date *</Label>
                      <Input
                        type="month"
                        value={newEducation.startDate}
                        onChange={(e) => setNewEducation({ ...newEducation, startDate: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Date</Label>
                      <Input
                        type="month"
                        value={newEducation.endDate}
                        onChange={(e) => setNewEducation({ ...newEducation, endDate: e.target.value })}
                        disabled={newEducation.current}
                      />
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id="current-edu"
                          checked={newEducation.current}
                          onChange={(e) => setNewEducation({ ...newEducation, current: e.target.checked, endDate: '' })}
                          className="rounded"
                        />
                        <Label htmlFor="current-edu" className="text-xs">Currently Studying</Label>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button type="button" onClick={handleAddEducation}>Add</Button>
                    <Button type="button" variant="outline" onClick={() => setShowEducationForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {educations.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <GraduationCap className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No education added yet</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {educations.map((edu, index) => (
                    <div key={index} className="p-4 border border-border rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-semibold">{edu.degree}</h4>
                          <p className="text-sm text-muted-foreground">{edu.institution}</p>
                          {edu.location && (
                            <p className="text-xs text-muted-foreground">{edu.location}</p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(edu.startDate).toLocaleDateString()} -{' '}
                            {edu.current ? 'Present' : new Date(edu.endDate).toLocaleDateString()}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveEducation(index)}
                        >
                          ×
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skills Section */}
          <Card>
            <CardHeader>
              <CardTitle>Skills</CardTitle>
              <CardDescription>Add your technical and professional skills</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddSkill())}
                  placeholder="Enter a skill and press Enter"
                />
                <Button type="button" onClick={handleAddSkill}>Add</Button>
              </div>
              {skills.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {skills.map((skill) => (
                    <div
                      key={skill}
                      className="flex items-center gap-2 px-3 py-1 bg-primary/10 text-primary rounded-full text-sm font-medium"
                    >
                      <span>{skill}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveSkill(skill)}
                        className="hover:text-primary/80"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground text-sm">
                  No skills added yet
                </div>
              )}
            </CardContent>
          </Card>

          {/* Submit Button */}
          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" onClick={() => navigate('/dashboard')}>
              Skip for Now
            </Button>
            <Button type="submit" size="lg" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Profile'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProfileSetup;




