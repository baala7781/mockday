
import React from 'react';
import { Card, CardContent } from '@/components/ui/card';

interface ReportMetric {
  name: string;
  value: number;
  color: 'primary' | 'green' | 'purple' | 'yellow';
}

interface ReportCardProps {
  title: string;
  metrics: ReportMetric[];
}

const ReportCard: React.FC<ReportCardProps> = ({ title, metrics }) => {
  return (
    <Card>
      <CardContent className="pt-6">
        <h3 className="text-lg font-medium mb-4">{title}</h3>
        <div className="space-y-4">
        {metrics.map((metric) => (
          <div key={metric.name} className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>{metric.name}</span>
              <span className="font-medium">{metric.value}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 ease-out ${
                  metric.color === 'primary' ? 'bg-primary' :
                  metric.color === 'green' ? 'bg-green-500' :
                  metric.color === 'purple' ? 'bg-purple-500' :
                  'bg-yellow-500'
                }`}
                style={{ 
                  width: `${metric.value}%`
                }}
              ></div>
            </div>
          </div>
        ))}
      </div>
      </CardContent>
    </Card>
  );
};

export default ReportCard;
