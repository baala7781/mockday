import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Calendar, Clock, TrendingUp, ArrowRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface InterviewCardProps {
  interview: {
    interview_id: string;
    report_id?: string;
    role: string;
    status: string;
    overall_score: number;
    created_at: string;
    total_questions?: number;
    recommendation?: string;
    completed_at?: string;
  };
}

const InterviewCard: React.FC<InterviewCardProps> = ({ interview }) => {
  const formatRole = (role: string) => {
    return role
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getRecommendationBadge = (recommendation?: string) => {
    if (!recommendation) return null;
    
    const colors = {
      hire: 'bg-green-500/10 text-green-700 dark:text-green-400',
      maybe: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
      no_hire: 'bg-red-500/10 text-red-700 dark:text-red-400',
    };
    
    const color = colors[recommendation as keyof typeof colors] || colors.maybe;
    const label = recommendation.charAt(0).toUpperCase() + recommendation.slice(1);
    
    return (
      <Badge className={color}>
        {label}
      </Badge>
    );
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return dateString;
    }
  };

  return (
    <Link to={`/interviews/${interview.interview_id}/report`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer border border-border">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <CardTitle className="text-lg mb-1">{formatRole(interview.role)}</CardTitle>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-3 w-3" />
                <span>{formatDate(interview.completed_at || interview.created_at)}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className={`text-2xl font-bold ${getScoreColor(interview.overall_score)}`}>
                {interview.overall_score}%
              </span>
              {getRecommendationBadge(interview.recommendation)}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-4 text-muted-foreground">
              {interview.total_questions && (
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  <span>{interview.total_questions} questions</span>
                </div>
              )}
              <Badge variant="outline" className="capitalize">
                {interview.status}
              </Badge>
            </div>
            <div className="flex items-center gap-1 text-primary">
              <span className="text-sm font-medium">View Report</span>
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
};

export default InterviewCard;

