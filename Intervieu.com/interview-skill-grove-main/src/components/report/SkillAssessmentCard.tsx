import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Brain, MessageSquare, Lightbulb } from 'lucide-react';

interface SkillScore {
  [skill: string]: number; // 0.0 to 1.0
}

interface SectionScores {
  technical?: number;
  communication?: number;
  problem_solving?: number;
  [key: string]: number | undefined;
}

interface SkillAssessmentCardProps {
  skillScores: SkillScore;
  sectionScores: SectionScores;
}

const SkillAssessmentCard: React.FC<SkillAssessmentCardProps> = ({ skillScores, sectionScores }) => {
  // Convert skill scores to percentages
  const skillPercentages = Object.entries(skillScores).map(([skill, score]) => ({
    name: skill,
    value: Math.round(score * 100)
  }));

  // Sort by value (highest first)
  skillPercentages.sort((a, b) => b.value - a.value);

  // Top 5 skills
  const topSkills = skillPercentages.slice(0, 5);

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-primary';
    if (score >= 40) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getScoreTextColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-primary';
    if (score >= 40) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Technical Skills */}
      <Card className="border-2">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-6">
            <Brain className="w-5 h-5 text-primary" />
            <h3 className="text-xl font-bold">Technical Skills</h3>
          </div>
          
          <div className="space-y-4">
            {topSkills.length > 0 ? (
              topSkills.map((skill) => (
                <div key={skill.name} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium capitalize">{skill.name}</span>
                    <span className={`text-sm font-bold ${getScoreTextColor(skill.value)}`}>
                      {skill.value}%
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getScoreColor(skill.value)} transition-all duration-500 ease-out`}
                      style={{ width: `${skill.value}%` }}
                    ></div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No technical skills assessed</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Soft Skills / Section Scores */}
      <Card className="border-2">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-6">
            <MessageSquare className="w-5 h-5 text-primary" />
            <h3 className="text-xl font-bold">Communication & Problem Solving</h3>
          </div>

          <div className="space-y-4">
            {sectionScores.communication !== undefined && (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Communication</span>
                  <span className={`text-sm font-bold ${getScoreTextColor(sectionScores.communication)}`}>
                    {sectionScores.communication}%
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${getScoreColor(sectionScores.communication)} transition-all duration-500 ease-out`}
                    style={{ width: `${sectionScores.communication}%` }}
                  ></div>
                </div>
              </div>
            )}

            {sectionScores.problem_solving !== undefined && (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1">
                    <Lightbulb className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Problem Solving</span>
                  </div>
                  <span className={`text-sm font-bold ${getScoreTextColor(sectionScores.problem_solving)}`}>
                    {sectionScores.problem_solving}%
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${getScoreColor(sectionScores.problem_solving)} transition-all duration-500 ease-out`}
                    style={{ width: `${sectionScores.problem_solving}%` }}
                  ></div>
                </div>
              </div>
            )}

            {sectionScores.technical !== undefined && (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Technical Knowledge</span>
                  <span className={`text-sm font-bold ${getScoreTextColor(sectionScores.technical)}`}>
                    {sectionScores.technical}%
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${getScoreColor(sectionScores.technical)} transition-all duration-500 ease-out`}
                    style={{ width: `${sectionScores.technical}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Other section scores */}
            {Object.entries(sectionScores)
              .filter(([key]) => !['technical', 'communication', 'problem_solving'].includes(key))
              .map(([key, value]) => value !== undefined && (
                <div key={key} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={`text-sm font-bold ${getScoreTextColor(value)}`}>
                      {value}%
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getScoreColor(value)} transition-all duration-500 ease-out`}
                      style={{ width: `${value}%` }}
                    ></div>
                  </div>
                </div>
              ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SkillAssessmentCard;

