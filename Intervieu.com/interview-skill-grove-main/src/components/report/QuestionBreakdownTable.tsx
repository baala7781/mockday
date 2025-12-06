import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Code, MessageCircle, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Question {
  question: string;
  answer?: string;
  type?: string;
  difficulty?: string;
  score?: number;
}

interface QuestionBreakdownTableProps {
  questions: string[];
  answers: string[];
}

const QuestionBreakdownTable: React.FC<QuestionBreakdownTableProps> = ({ questions, answers }) => {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);

  if (!questions || questions.length === 0) {
    return null;
  }

  const getQuestionIcon = (question: string) => {
    const lowerQ = question.toLowerCase();
    if (lowerQ.includes('code') || lowerQ.includes('implement') || lowerQ.includes('algorithm')) {
      return <Code className="w-4 h-4 text-primary" />;
    } else if (lowerQ.includes('explain') || lowerQ.includes('describe') || lowerQ.includes('what is')) {
      return <MessageCircle className="w-4 h-4 text-green-500" />;
    }
    return <FileText className="w-4 h-4 text-muted-foreground" />;
  };

  const getScoreBadge = (score: number) => {
    if (score >= 90) {
      return <Badge className="bg-green-500">Excellent</Badge>;
    } else if (score >= 75) {
      return <Badge className="bg-primary">Good</Badge>;
    } else if (score >= 60) {
      return <Badge className="bg-yellow-500">Fair</Badge>;
    }
    return <Badge variant="destructive">Needs Improvement</Badge>;
  };

  // Extract score from answer feedback if available
  const extractScore = (answer: string, index: number): number => {
    const scoreMatch = answer.match(/score[:\s]*(\d+)/i);
    if (scoreMatch) return parseInt(scoreMatch[1]);
    
    // Default score estimation based on answer length and keywords
    if (answer.includes('excellent') || answer.includes('strong')) return 85;
    if (answer.includes('good') || answer.includes('solid')) return 75;
    if (answer.includes('fair') || answer.includes('adequate')) return 65;
    if (answer.includes('weak') || answer.includes('poor')) return 50;
    
    // Default based on position (later questions might be harder)
    return Math.max(60, 80 - Math.floor(index / 3) * 5);
  };

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <h3 className="text-2xl font-bold mb-6">Question-by-Question Analysis</h3>

        <div className="space-y-3">
          {questions.map((question, index) => {
            const answer = answers[index] || 'Answer provided';
            const score = extractScore(answer, index);
            const isExpanded = expandedIndex === index;

            return (
              <div
                key={index}
                className="border border-border rounded-lg overflow-hidden transition-all hover:border-primary/50"
              >
                {/* Question Header */}
                <div
                  className="p-4 bg-muted/30 cursor-pointer flex items-start gap-3"
                  onClick={() => toggleExpand(index)}
                >
                  <div className="flex-shrink-0 mt-1">
                    {getQuestionIcon(question)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3 mb-1">
                      <h4 className="font-medium text-sm leading-tight">
                        <span className="text-muted-foreground mr-2">Q{index + 1}.</span>
                        {question}
                      </h4>
                      {getScoreBadge(score)}
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(index);
                    }}
                  >
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </Button>
                </div>

                {/* Answer / Feedback (Expandable) */}
                {isExpanded && (
                  <div className="p-4 bg-background border-t">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {answer}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

export default QuestionBreakdownTable;

