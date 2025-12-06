import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Code, CheckCircle2, XCircle, TrendingUp } from 'lucide-react';

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

interface CodingPerformanceCardProps {
  codingPerformance: CodingPerformance;
}

const CodingPerformanceCard: React.FC<CodingPerformanceCardProps> = ({ codingPerformance }) => {
  if (codingPerformance.total_coding_questions === 0) {
    return null; // Don't show if no coding questions
  }

  const { total_coding_questions, coding_questions_solved, success_rate, by_difficulty } = codingPerformance;

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy':
        return 'bg-green-500';
      case 'medium':
        return 'bg-yellow-500';
      case 'hard':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getDifficultyLabel = (difficulty: string) => {
    return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
  };

  const calculatePercentage = (solved: number, attempted: number) => {
    return attempted > 0 ? Math.round((solved / attempted) * 100) : 0;
  };

  return (
    <Card className="border-2">
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 mb-6">
          <Code className="w-6 h-6 text-primary" />
          <h3 className="text-2xl font-bold">Coding Performance</h3>
        </div>

        {/* Overall Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="bg-muted/50 p-4 rounded-lg text-center">
            <p className="text-sm text-muted-foreground mb-1">Attempted</p>
            <p className="text-3xl font-bold">{total_coding_questions}</p>
          </div>

          <div className="bg-green-500/10 p-4 rounded-lg text-center border border-green-500/20">
            <p className="text-sm text-muted-foreground mb-1">Solved</p>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400">{coding_questions_solved}</p>
          </div>

          <div className="bg-muted/50 p-4 rounded-lg text-center">
            <p className="text-sm text-muted-foreground mb-1">Success Rate</p>
            <p className="text-3xl font-bold">{success_rate}%</p>
          </div>

          <div className="bg-primary/10 p-4 rounded-lg text-center border border-primary/20">
            <div className="flex items-center justify-center gap-1 mb-1">
              <TrendingUp className="w-4 h-4 text-primary" />
              <p className="text-sm text-muted-foreground">Performance</p>
            </div>
            <p className="text-2xl font-bold text-primary">
              {success_rate >= 80 ? 'Excellent' : success_rate >= 60 ? 'Good' : 'Fair'}
            </p>
          </div>
        </div>

        {/* Difficulty Breakdown */}
        <div className="space-y-4">
          <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">By Difficulty</h4>
          
          {Object.entries(by_difficulty).map(([difficulty, stats]) => {
            if (stats.attempted === 0) return null;
            
            const percentage = calculatePercentage(stats.solved, stats.attempted);
            const colorClass = getDifficultyColor(difficulty);
            
            return (
              <div key={difficulty} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${colorClass}`}></span>
                    <span className="font-medium">{getDifficultyLabel(difficulty)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">
                      {stats.solved}/{stats.attempted}
                    </span>
                    <span className="font-semibold min-w-[3rem] text-right">{percentage}%</span>
                  </div>
                </div>
                
                <div className="h-3 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${colorClass} transition-all duration-500 ease-out`}
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Performance Indicators */}
        <div className="mt-6 pt-6 border-t grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="w-5 h-5 text-green-500" />
            <span className="text-muted-foreground">Solved: <span className="font-semibold text-foreground">{coding_questions_solved}</span></span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <XCircle className="w-5 h-5 text-muted-foreground" />
            <span className="text-muted-foreground">Unsolved: <span className="font-semibold text-foreground">{total_coding_questions - coding_questions_solved}</span></span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default CodingPerformanceCard;

