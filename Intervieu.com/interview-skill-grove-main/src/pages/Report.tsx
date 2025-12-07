
import React, { useState, useEffect } from 'react';
import { useSearchParams, useParams } from 'react-router-dom';
import { Download, Share, Loader2, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { interviewService } from '@/services/interviewService';

// New Report Components
import ExecutiveSummary from '@/components/report/ExecutiveSummary';
import CodingPerformanceCard from '@/components/report/CodingPerformanceCard';
import SkillAssessmentCard from '@/components/report/SkillAssessmentCard';
import QuestionBreakdownTable from '@/components/report/QuestionBreakdownTable';
import ImprovementPlan from '@/components/report/ImprovementPlan';

interface CodingPerformance {
  total_coding_questions: number;
  coding_questions_solved: number;
  success_rate: number;
  by_difficulty: {
    easy: { attempted: number; solved: number };
    medium: { attempted: number; solved: number };
    hard: { attempted: number; solved: number };
  };
}

interface ReportData {
  overall_score: number | null;
  section_scores: {
    technical?: number;
    communication?: number;
    problem_solving?: number;
    [key: string]: number | undefined;
  };
  strengths: string[];
  weaknesses: string[];
  detailed_feedback: string;
  recommendation: string;
  improvement_suggestions: string[];
  skill_scores?: { [key: string]: number };
  coding_performance?: CodingPerformance;
  questions?: string[];
  answers?: string[];
  role?: string;
  total_questions?: number;
  questions_answered?: number;
  interview_duration?: number;
  created_at?: string;
  is_complete?: boolean;
  completion_warning?: string;
  completion_percentage?: number;
}

const Report: React.FC = () => {
  // Support both URL params (/interviews/:interviewId/report) and query params (/report?interviewId=...)
  const params = useParams<{ interviewId: string }>();
  const [searchParams] = useSearchParams();
  const interviewId = params.interviewId || searchParams.get('interviewId');
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const reportCacheRef = React.useRef<Map<string, { data: ReportData; timestamp: number }>>(new Map());
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  useEffect(() => {
    const fetchReport = async () => {
      if (!interviewId) {
        setError('No interview ID provided');
        setLoading(false);
        return;
      }

      // Check cache first
      const cached = reportCacheRef.current.get(interviewId);
      const now = Date.now();
      if (cached && (now - cached.timestamp) < CACHE_DURATION) {
        console.log('Using cached report');
        setReportData(cached.data);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        
        // Retry logic for report generation
        let attempts = 0;
        const maxAttempts = 10;
        const retryDelay = 2000; // 2 seconds

        while (attempts < maxAttempts) {
          try {
            const report = await interviewService.getInterviewReport(interviewId);
            setReportData(report);
            
            // Update cache
            reportCacheRef.current.set(interviewId, { data: report, timestamp: now });
            
            setLoading(false);
            return;
          } catch (err: any) {
            if (err.message.includes('being generated') && attempts < maxAttempts - 1) {
              // Report is still being generated, wait and retry
              attempts++;
              await new Promise(resolve => setTimeout(resolve, retryDelay));
              continue;
            }
            throw err;
          }
        }
      } catch (err: any) {
        console.error('Error fetching report:', err);
        setError(err.message || 'Failed to load report');
        setLoading(false);
        toast({
          variant: 'destructive',
          title: 'Error',
          description: err.message || 'Failed to load report',
        });
      }
    };

    fetchReport();
  }, [interviewId, toast]);


  if (loading) {
    return (
      <div className="page-container py-12">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
          <p className="text-foreground/70">Generating your report...</p>
          <p className="text-sm text-foreground/50 mt-2">This may take a few moments</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container py-12">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <AlertCircle className="w-12 h-12 text-destructive mb-4" />
          <h2 className="text-2xl font-medium mb-2">Error Loading Report</h2>
          <p className="text-foreground/70 mb-6">{error}</p>
          <div className="flex gap-4">
            <Button asChild>
              <Link to="/dashboard">Back to Dashboard</Link>
            </Button>
            {interviewId && (
              <Button variant="outline" onClick={() => window.location.reload()}>
                Retry
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!reportData) {
    return (
      <div className="page-container py-12">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <AlertCircle className="w-12 h-12 text-destructive mb-4" />
          <h2 className="text-2xl font-medium mb-2">Report Not Found</h2>
          <p className="text-foreground/70 mb-6">Unable to load report data.</p>
          <Button asChild>
            <Link to="/dashboard">Back to Dashboard</Link>
          </Button>
        </div>
      </div>
    );
  }

  const overallScore = reportData.overall_score ?? null;

  return (
    <div className="page-transition">
      <div className="page-container py-12">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">Interview Performance Report</h1>
            <p className="text-muted-foreground">
              Comprehensive analysis of your interview performance
            </p>
          </div>
          
          <div className="flex gap-4">
            <Button variant="outline" className="flex items-center gap-2">
              <Download size={18} />
              <span>Download PDF</span>
            </Button>
            <Button variant="outline" className="flex items-center gap-2">
              <Share size={18} />
              <span>Share</span>
            </Button>
          </div>
        </div>

        {/* Executive Summary */}
        <ExecutiveSummary
          overallScore={overallScore}
          recommendation={reportData.recommendation}
          role={reportData.role || 'Interview'}
          duration={reportData.interview_duration || 0}
          questionsAnswered={reportData.questions_answered || reportData.questions?.length || 0}
          totalQuestions={reportData.total_questions || 12}
          detailedFeedback={reportData.detailed_feedback}
          createdAt={reportData.created_at || new Date().toISOString()}
          isComplete={reportData.is_complete !== false}
          completionWarning={reportData.completion_warning}
        />

        {/* Coding Performance (if applicable) */}
        {reportData.coding_performance && reportData.coding_performance.total_coding_questions > 0 && (
          <div className="mb-8">
            <CodingPerformanceCard codingPerformance={reportData.coding_performance} />
          </div>
        )}

        {/* Skill Assessment */}
        {(reportData.skill_scores || reportData.section_scores) && (
          <div className="mb-8">
            <SkillAssessmentCard
              skillScores={reportData.skill_scores || {}}
              sectionScores={reportData.section_scores}
            />
          </div>
        )}

        {/* Question Breakdown */}
        {reportData.questions && reportData.questions.length > 0 && (
          <div className="mb-8">
            <QuestionBreakdownTable
              questions={reportData.questions}
              answers={reportData.answers || []}
            />
          </div>
        )}

        {/* Improvement Plan */}
        <div className="mb-8">
          <ImprovementPlan
            strengths={reportData.strengths}
            weaknesses={reportData.weaknesses}
            improvementSuggestions={reportData.improvement_suggestions}
            skillScores={reportData.skill_scores}
          />
        </div>

        {/* Call to Action */}
        <Card className="text-center bg-gradient-to-br from-primary/5 to-transparent">
          <CardContent className="pt-8 pb-8">
            <h2 className="text-2xl font-bold mb-3">Ready for Your Next Challenge?</h2>
            <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
              Keep practicing to improve your skills and track your progress over time. Each interview helps you get one step closer to your dream role.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Button asChild size="lg">
                <Link to="/start-interview">Start New Interview</Link>
              </Button>
              <Button variant="outline" asChild size="lg">
                <Link to="/dashboard">Back to Dashboard</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Report;
