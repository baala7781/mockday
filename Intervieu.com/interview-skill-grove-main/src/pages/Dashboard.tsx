
import React, { useState, useEffect } from 'react';
import { Calendar, Clock, BarChart2, Award, Briefcase, BrainCircuit, Sparkles, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { interviewService } from '@/services/interviewService';
import InterviewCard from '@/components/InterviewCard';
import { useToast } from '@/hooks/use-toast';

// --- Reusable Components ---

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

const StatCard: React.FC<StatCardProps> = ({ icon, label, value }) => (
  <div className="bg-card p-5 rounded-lg flex items-center shadow-sm border border-border">
    <div className="mr-4 text-primary">{icon}</div>
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold text-card-foreground">{value}</p>
    </div>
  </div>
);

// --- Main Dashboard Component ---

interface Interview {
  interview_id: string;
  report_id?: string;
  role: string;
  status: string;
  overall_score: number;
  created_at: string;
  total_questions?: number;
  recommendation?: string;
  completed_at?: string;
}

const Dashboard: React.FC = () => {
  const { currentUser } = useAuth();
  const userName = currentUser?.displayName?.split(' ')[0] || 'Candidate';
  const [profileComplete, setProfileComplete] = useState(false);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalInterviews: 0,
    averageScore: 0,
    hoursPracticed: 0,
    scheduledInterviews: 0
  });
  const { toast } = useToast();
  const CACHE_KEY = `interviews_cache_${currentUser?.uid || 'anon'}`;
  const CACHE_DURATION = 2 * 60 * 1000; // 2 minutes

  // Load from sessionStorage on mount
  const getCachedData = (): { data: Interview[]; timestamp: number } | null => {
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        return JSON.parse(cached);
      }
    } catch (e) {
      console.debug('Cache read error:', e);
    }
    return null;
  };

  const setCachedData = (data: Interview[]) => {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ data, timestamp: Date.now() }));
    } catch (e) {
      console.debug('Cache write error:', e);
    }
  };

  useEffect(() => {
    // Check if profile is complete
    setProfileComplete(!!currentUser?.displayName);
  }, [currentUser]);

  useEffect(() => {
    const fetchInterviews = async () => {
      if (!currentUser) return;
      
      // Check sessionStorage cache first (persists across page navigation)
      const now = Date.now();
      const cached = getCachedData();
      if (cached && cached.data && (now - cached.timestamp) < CACHE_DURATION) {
        setInterviews(cached.data);
        calculateStats(cached.data);
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        const data = await interviewService.getInterviews();
        const interviewsData = data || [];
        setInterviews(interviewsData);
        
        // Update sessionStorage cache
        setCachedData(interviewsData);
        
        calculateStats(interviewsData);
      } catch (error: any) {
        console.error('Error fetching interviews:', error);
        // If we have stale cache, use it as fallback
        const staleCache = getCachedData();
        if (staleCache && staleCache.data) {
          setInterviews(staleCache.data);
          calculateStats(staleCache.data);
        }
        toast({
          variant: 'destructive',
          title: 'Error',
          description: error.message || 'Failed to load interviews',
        });
      } finally {
        setLoading(false);
      }
    };

    const calculateStats = (data: Interview[]) => {
      if (data && data.length > 0) {
        const completed = data.filter(i => i.status === 'completed');
        const totalScore = completed.reduce((sum, i) => sum + (i.overall_score || 0), 0);
        const avgScore = completed.length > 0 ? Math.round(totalScore / completed.length) : 0;
        
        // Estimate hours practiced (assuming ~30 min per interview)
        const hoursPracticed = Math.round((completed.length * 0.5) * 10) / 10;
        
        setStats({
          totalInterviews: completed.length,
          averageScore: avgScore,
          hoursPracticed: hoursPracticed,
          scheduledInterviews: data.filter(i => i.status === 'in_progress' || i.status === 'not_started').length
        });
      }
    };

    fetchInterviews();
  }, [currentUser, toast]);

  return (
    <div className="page-container py-8">

      {/* Profile Setup Alert */}
      {!profileComplete && (
        <Alert className="mb-6 border-primary/20 bg-primary/5">
          <Sparkles className="h-4 w-4 text-primary" />
          <AlertTitle>Complete Your Profile</AlertTitle>
          <AlertDescription className="flex items-center justify-between flex-wrap gap-3">
            <span>Set up your profile to get personalized interview experiences tailored to your background.</span>
            <Button asChild size="sm">
              <Link to="/profile/setup">Complete Setup</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Welcome back, {userName}!</h1>
          <p className="text-lg text-muted-foreground mt-1">Ready to ace your next interview? Let's get started.</p>
        </div>
        <Button asChild size="lg" className="mt-4 sm:mt-0 shadow-sm">
          <Link to="/start-interview">Start Mock Interview</Link>
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard icon={<Calendar size={28} />} label="Scheduled Interviews" value={stats.scheduledInterviews.toString()} />
        <StatCard icon={<Clock size={28} />} label="Hours Practiced" value={stats.hoursPracticed.toString()} />
        <StatCard icon={<BarChart2 size={28} />} label="Average Score" value={stats.averageScore > 0 ? `${stats.averageScore}%` : '--'} />
        <StatCard icon={<Award size={28} />} label="Mocks Completed" value={stats.totalInterviews.toString()} />
      </div>
      
      {/* Activity Tabs */}
      <Tabs defaultValue="mock-interviews">
        <TabsList className="grid w-full grid-cols-1 md:w-1/2 lg:w-1/3 mb-4">
          <TabsTrigger value="mock-interviews">
            <BrainCircuit className="mr-2 h-4 w-4"/> My Mock Interviews
          </TabsTrigger>
        </TabsList>

        {/* Mock Interviews Content */}
        <TabsContent value="mock-interviews">
          <Card className="border border-border">
            <CardHeader>
              <CardTitle>Practice History</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : interviews.length === 0 ? (
                <div className="text-center py-12">
                  <BrainCircuit className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">No interviews yet</h3>
                  <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                    Start your first mock interview to see your practice history and detailed feedback here.
                  </p>
                  <Button asChild>
                    <Link to="/start-interview">Start Your First Interview</Link>
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {interviews.map((interview) => (
                    <InterviewCard key={interview.interview_id} interview={interview} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

    </div>
  );
};

export default Dashboard;
