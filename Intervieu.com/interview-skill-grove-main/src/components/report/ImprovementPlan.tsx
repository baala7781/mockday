import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, AlertCircle, CheckCircle2, BookOpen, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ImprovementPlanProps {
  strengths: string[];
  weaknesses: string[];
  improvementSuggestions: string[];
  skillScores?: { [key: string]: number };
}

const ImprovementPlan: React.FC<ImprovementPlanProps> = ({
  strengths,
  weaknesses,
  improvementSuggestions,
  skillScores
}) => {
  // Identify skill gaps (skills below 60%)
  const skillGaps = skillScores 
    ? Object.entries(skillScores)
        .filter(([_, score]) => score < 0.6)
        .map(([skill, score]) => ({ skill, score: Math.round(score * 100) }))
        .sort((a, b) => a.score - b.score)
    : [];

  // Get recommended resources based on weak skills
  const getResourceRecommendations = () => {
    const resources = [];
    
    if (skillGaps.length > 0) {
      const topGap = skillGaps[0].skill.toLowerCase();
      
      if (topGap.includes('algorithm') || topGap.includes('data structure')) {
        resources.push({
          title: 'LeetCode - Algorithm Practice',
          url: 'https://leetcode.com',
          description: 'Practice coding problems to strengthen algorithmic thinking'
        });
      }
      
      if (topGap.includes('python') || topGap.includes('javascript')) {
        resources.push({
          title: `${skillGaps[0].skill} Documentation`,
          url: '#',
          description: 'Review official documentation and best practices'
        });
      }
      
      if (topGap.includes('system')) {
        resources.push({
          title: 'System Design Primer',
          url: 'https://github.com/donnemartin/system-design-primer',
          description: 'Comprehensive guide to system design interviews'
        });
      }
    }
    
    return resources;
  };

  const resources = getResourceRecommendations();

  return (
    <div className="space-y-6">
      {/* Strengths & Weaknesses */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Strengths */}
        <Card className="border-2 border-green-500/20">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle2 className="w-5 h-5 text-green-500" />
              <h3 className="text-xl font-bold">Key Strengths</h3>
              <Badge className="bg-green-500 ml-auto">{strengths.length}</Badge>
            </div>
            
            {strengths.length > 0 ? (
              <ul className="space-y-3">
                {strengths.map((strength, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-green-500 mt-1">✓</span>
                    <p className="text-sm leading-relaxed">{strength}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No specific strengths identified</p>
            )}
          </CardContent>
        </Card>

        {/* Weaknesses */}
        <Card className="border-2 border-yellow-500/20">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-5 h-5 text-yellow-500" />
              <h3 className="text-xl font-bold">Areas for Improvement</h3>
              <Badge className="bg-yellow-500 ml-auto">{weaknesses.length}</Badge>
            </div>
            
            {weaknesses.length > 0 ? (
              <ul className="space-y-3">
                {weaknesses.map((weakness, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-yellow-500 mt-1">△</span>
                    <p className="text-sm leading-relaxed">{weakness}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No major weaknesses identified</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Skill Gaps */}
      {skillGaps.length > 0 && (
        <Card className="border-2">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="text-xl font-bold">Skill Gap Analysis</h3>
            </div>

            <p className="text-sm text-muted-foreground mb-4">
              Focus on these areas to improve your interview readiness:
            </p>

            <div className="space-y-3">
              {skillGaps.slice(0, 3).map(({ skill, score }, index) => (
                <div key={index} className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <div className="flex-1">
                    <p className="font-medium capitalize text-sm">{skill}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
                        <div
                          className="h-full bg-yellow-500"
                          style={{ width: `${score}%` }}
                        ></div>
                      </div>
                      <span className="text-xs text-muted-foreground min-w-[3rem] text-right">{score}%</span>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Priority {index + 1}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Plan */}
      <Card className="border-2 border-primary/20">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-5 h-5 text-primary" />
            <h3 className="text-xl font-bold">Personalized Action Plan</h3>
          </div>

          {improvementSuggestions.length > 0 ? (
            <ol className="space-y-3 mb-6">
              {improvementSuggestions.map((suggestion, index) => (
                <li key={index} className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-bold flex-shrink-0">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-relaxed pt-0.5">{suggestion}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted-foreground mb-6">Keep practicing and refining your skills!</p>
          )}

          {/* Recommended Resources */}
          {resources.length > 0 && (
            <div className="pt-4 border-t">
              <h4 className="font-semibold text-sm mb-3">Recommended Resources:</h4>
              <div className="space-y-2">
                {resources.map((resource, index) => (
                  <a
                    key={index}
                    href={resource.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors group"
                  >
                    <ExternalLink className="w-4 h-4 text-primary mt-0.5 flex-shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">{resource.title}</p>
                      <p className="text-xs text-muted-foreground">{resource.description}</p>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ImprovementPlan;

