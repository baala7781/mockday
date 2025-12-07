import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Clock, CheckCircle, Target } from 'lucide-react';

interface ExecutiveSummaryProps {
  overallScore: number | null;
  recommendation: string;
  role: string;
  duration: number; // in minutes
  questionsAnswered: number;
  totalQuestions: number;
  detailedFeedback?: string;
  createdAt: string;
  isComplete?: boolean;
  completionWarning?: string;
}

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({
  overallScore,
  recommendation,
  role,
  duration,
  questionsAnswered,
  totalQuestions,
  detailedFeedback,
  createdAt,
  isComplete = true,
  completionWarning
}) => {
  // Format recommendation
  const getRecommendationBadge = () => {
    const rec = recommendation.toLowerCase();
    if (rec === 'no_assessment' || overallScore === null || overallScore === undefined) {
      return { label: 'NO ASSESSMENT', variant: 'secondary' as const, color: 'bg-gray-500' };
    } else if (rec === 'hire' || rec.includes('strong')) {
      return { label: 'STRONG HIRE', variant: 'default' as const, color: 'bg-green-500' };
    } else if (rec === 'maybe' || rec.includes('consider')) {
      return { label: 'CONSIDER', variant: 'secondary' as const, color: 'bg-yellow-500' };
    } else {
      return { label: 'NO HIRE', variant: 'destructive' as const, color: 'bg-red-500' };
    }
  };

  const badge = getRecommendationBadge();

  // Calculate role match (based on score) - only if score exists
  const roleMatch = overallScore !== null && overallScore !== undefined 
    ? Math.min(100, Math.round(overallScore * 1.15))
    : null;
  
  const hasScore = overallScore !== null && overallScore !== undefined;

  // Format date
  const formattedDate = new Date(createdAt).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  return (
    <Card className="mb-8 border-2">
      <CardContent className="pt-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-8">
          {/* Score Circle */}
          <div className="relative flex-shrink-0">
            {hasScore ? (
              <>
                <svg className="w-40 h-40 lg:w-48 lg:h-48 transform -rotate-90">
                  <circle
                    className="text-muted"
                    strokeWidth="10"
                    stroke="currentColor"
                    fill="transparent"
                    r="60"
                    cx="80"
                    cy="80"
                  />
                  <circle
                    className={`${overallScore >= 80 ? 'text-green-500' : overallScore >= 60 ? 'text-primary' : 'text-yellow-500'} transition-all duration-1000`}
                    strokeWidth="10"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="transparent"
                    r="60"
                    cx="80"
                    cy="80"
                    strokeDasharray={377}
                    strokeDashoffset={377 - (377 * overallScore) / 100}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-4xl lg:text-5xl font-bold">{overallScore}</span>
                  <span className="text-sm text-muted-foreground">out of 100</span>
                </div>
              </>
            ) : (
              <div className="w-40 h-40 lg:w-48 lg:h-48 rounded-full bg-muted flex flex-col items-center justify-center border-4 border-dashed border-muted-foreground/30">
                <span className="text-2xl lg:text-3xl font-bold text-muted-foreground">N/A</span>
                <span className="text-xs text-muted-foreground mt-1">No Score</span>
              </div>
            )}
          </div>

          {/* Summary Details */}
          <div className="flex-1 space-y-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-2xl lg:text-3xl font-bold">Interview Report</h2>
                <Badge className={badge.color} variant={badge.variant}>
                  {badge.label}
                </Badge>
              </div>
              <p className="text-lg text-muted-foreground">
                {role.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} • {formattedDate}
              </p>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="flex items-center gap-2 bg-muted/50 p-3 rounded-lg">
                <Target className="w-5 h-5 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">Role Match</p>
                  <p className="text-lg font-semibold">{roleMatch !== null ? `${roleMatch}%` : 'N/A'}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 bg-muted/50 p-3 rounded-lg">
                <Clock className="w-5 h-5 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">Duration</p>
                  <p className="text-lg font-semibold">{Math.round(duration)} min</p>
                </div>
              </div>

              <div className="flex items-center gap-2 bg-muted/50 p-3 rounded-lg">
                <CheckCircle className="w-5 h-5 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">Questions</p>
                  <p className="text-lg font-semibold">{questionsAnswered}/{totalQuestions}</p>
                </div>
              </div>
            </div>

            {/* Incomplete Interview Warning */}
            {!isComplete && (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg border-l-4 border-yellow-500">
                <p className="text-sm text-yellow-800 dark:text-yellow-200 font-medium">
                  ⚠️ {completionWarning || `Incomplete Interview: Only ${questionsAnswered} of ${totalQuestions} questions were answered. Scores may not reflect full potential.`}
                </p>
              </div>
            )}

            {/* Feedback */}
            {detailedFeedback && (
              <div className="bg-muted/30 p-4 rounded-lg border-l-4 border-primary">
                <p className="text-sm leading-relaxed">{detailedFeedback}</p>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ExecutiveSummary;

