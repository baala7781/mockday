import React, { useState, useEffect, useMemo } from 'react';
import { Briefcase, Mail, MapPin, User, FileText, Plus, GraduationCap, Linkedin, ExternalLink, Award, Sparkles, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import ProfileEditForm from './ProfileEditForm';
import { useToast } from "@/hooks/use-toast";

const ProfileDetails: React.FC = () => {
  const { currentUser, profile: profileData, resumes: resumesData } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  // Use cached data from AuthContext - no API calls needed
  const profile = useMemo(() => ({
    name: profileData?.name || currentUser?.displayName || '',
    email: currentUser?.email || '',
    location: profileData?.location || '',
    experienceLevel: profileData?.experienceLevel || '',
    linkedinUrl: profileData?.linkedinUrl || '',
    bio: profileData?.bio || '',
  }), [profileData, currentUser]);

  const experiences = useMemo(() => {
    // Transform profileData.experiences if available
    return profileData?.experiences || [];
  }, [profileData]);

  const educations = useMemo(() => {
    // Transform profileData.educations if available
    return profileData?.educations || [];
  }, [profileData]);

  const skills = useMemo(() => profileData?.skills || [], [profileData]);
  
  const resumes = useMemo(() => {
    return (resumesData || []).map(r => ({ 
      id: r.id, 
      name: r.name, 
      uploadedAt: r.uploadedAt || new Date().toISOString() 
    }));
  }, [resumesData]);

  const isProfileComplete = useMemo(() => {
    return !!(profile.name || currentUser?.displayName) && !!profile.experienceLevel;
  }, [profile.name, profile.experienceLevel, currentUser]);

  const handleProfileUpdate = () => {
    // TODO: Reload from API after update
    toast({
      title: "Profile Updated",
      description: "Your profile has been refreshed.",
    });
  };

  // Show setup prompt if profile incomplete
  if (!isProfileComplete) {
    return (
      <div className="max-w-3xl mx-auto">
        <Alert className="mb-6">
          <Sparkles className="h-4 w-4" />
          <AlertDescription>
            Complete your profile to get personalized interview experiences. 
            <Button 
              type="button"
              variant="link" 
              className="p-0 h-auto ml-2"
              onClick={(e) => {
                e.preventDefault();
                navigate('/profile/setup');
              }}
            >
              Set up now
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Profile Header Card */}
      <Card className="border-border shadow-sm">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            <div className="relative">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border-4 border-primary/10">
                {currentUser?.photoURL ? (
                  <img 
                    src={currentUser.photoURL} 
                    alt={profile.name}
                    className="w-full h-full rounded-full object-cover"
                  />
                ) : (
                  <User size={48} className="text-primary" />
                )}
              </div>
              <div className="absolute bottom-0 right-0 bg-primary text-primary-foreground rounded-full p-1.5 border-2 border-background">
                <CheckCircle2 size={16} />
              </div>
            </div>
            
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-2xl font-bold text-foreground">{profile.name}</h2>
                {profile.experienceLevel && (
                  <Badge variant="secondary" className="text-xs">
                    {profile.experienceLevel}
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground mb-3">
                {profile.location && (
                  <div className="flex items-center gap-1.5">
                    <MapPin size={14} />
                    <span>{profile.location}</span>
                  </div>
                )}
                {profile.email && (
                  <div className="flex items-center gap-1.5">
                    <Mail size={14} />
                    <span>{profile.email}</span>
                  </div>
                )}
                {profile.linkedinUrl && (
                  <a 
                    href={profile.linkedinUrl} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 hover:text-primary transition-colors"
                  >
                    <Linkedin size={14} />
                    <span>LinkedIn</span>
                    <ExternalLink size={12} />
                  </a>
                )}
              </div>
              {profile.bio && (
                <p className="text-foreground/80 text-sm leading-relaxed">{profile.bio}</p>
              )}
            </div>

            <div className="flex gap-2">
              <ProfileEditForm onSave={handleProfileUpdate} />
              <Button 
                variant="outline" 
                onClick={() => navigate('/profile/setup')}
              >
                Complete Setup
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Quick Stats */}
        <div className="lg:col-span-1 space-y-6">
          {/* Resume Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Resumes</CardTitle>
              <CardDescription>Manage your uploaded resumes</CardDescription>
            </CardHeader>
            <CardContent>
              {resumes.length === 0 ? (
                <div className="text-center py-6">
                  <FileText className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                  <p className="text-sm text-muted-foreground mb-3">No resumes uploaded</p>
                  <Button variant="outline" size="sm" onClick={() => navigate('/profile/setup')}>
                    <Plus className="h-4 w-4 mr-2" />
                    Upload Resume
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {resumes.map((resume) => (
                    <div
                      key={resume.id}
                      className="flex items-center justify-between p-3 border border-border rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-primary" />
                        <div>
                          <p className="text-sm font-medium">{resume.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(resume.uploadedAt).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        Active
                      </Badge>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="w-full mt-2">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Resume
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skills Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Skills</CardTitle>
            </CardHeader>
            <CardContent>
              {skills.length === 0 ? (
                <div className="text-center py-6">
                  <Award className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                  <p className="text-sm text-muted-foreground mb-3">No skills added</p>
                  <Button variant="outline" size="sm" onClick={() => navigate('/profile/setup')}>
                    Add Skills
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {skills.map((skill) => (
                    <Badge key={skill} variant="secondary" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 px-2 text-xs"
                    onClick={() => navigate('/profile/setup')}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Experience & Education */}
        <div className="lg:col-span-2 space-y-6">
          {/* Experience Section */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Work Experience</CardTitle>
                  <CardDescription>Your professional experience</CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => navigate('/profile/setup')}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Experience
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {experiences.length === 0 ? (
                <div className="text-center py-12">
                  <Briefcase className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <h3 className="text-lg font-semibold mb-2">No experience added</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Add your work experience to help us personalize your interviews
                  </p>
                  <Button onClick={() => navigate('/profile/setup')}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Experience
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  {experiences.map((exp, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center border-2 border-primary/20">
                          <Briefcase className="h-5 w-5 text-primary" />
                        </div>
                        {index < experiences.length - 1 && (
                          <div className="w-0.5 h-full bg-border my-2"></div>
                        )}
                      </div>
                      <div className="flex-1 pb-6">
                        <h4 className="font-semibold text-foreground mb-1">{exp.role}</h4>
                        <p className="text-sm font-medium text-primary mb-1">{exp.company}</p>
                        {exp.location && (
                          <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                            <MapPin size={12} />
                            {exp.location}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">{exp.period}</p>
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
                  <CardDescription>Your educational background</CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => navigate('/profile/setup')}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Education
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {educations.length === 0 ? (
                <div className="text-center py-12">
                  <GraduationCap className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <h3 className="text-lg font-semibold mb-2">No education added</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Add your educational background to complete your profile
                  </p>
                  <Button onClick={() => navigate('/profile/setup')}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Education
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  {educations.map((edu, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center border-2 border-green-500/20">
                          <GraduationCap className="h-5 w-5 text-green-600 dark:text-green-400" />
                        </div>
                        {index < educations.length - 1 && (
                          <div className="w-0.5 h-full bg-border my-2"></div>
                        )}
                      </div>
                      <div className="flex-1 pb-6">
                        <h4 className="font-semibold text-foreground mb-1">{edu.degree}</h4>
                        <p className="text-sm font-medium text-foreground/80 mb-1">{edu.institution}</p>
                        {edu.location && (
                          <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                            <MapPin size={12} />
                            {edu.location}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">{edu.period}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ProfileDetails;
