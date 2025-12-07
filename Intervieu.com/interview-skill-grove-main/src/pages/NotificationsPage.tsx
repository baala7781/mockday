
import React, { useState } from 'react';
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from '@/components/ui/button';

// A reusable component for each notification setting row
const NotificationSetting: React.FC<{ title: string; description: string; initialChecked: boolean; }> = ({ title, description, initialChecked }) => {
  const [isChecked, setIsChecked] = useState(initialChecked);

  return (
    <div className="flex items-center justify-between py-5 border-b border-border last:border-b-0">
      <div>
        <h4 className="font-semibold text-card-foreground">{title}</h4>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Switch
        checked={isChecked}
        onCheckedChange={setIsChecked}
        aria-label={title}
      />
    </div>
  );
};

// The main page component
const NotificationsPage: React.FC = () => {
  const notificationSettings = [
    {
      title: 'Email Notifications',
      description: 'Receive emails about your account, new features, and updates.',
      initialChecked: true,
    },
    {
      title: 'Interview Reminders',
      description: 'Get reminders for your upcoming scheduled interviews.',
      initialChecked: true,
    },
    {
      title: 'Feedback & Reports',
      description: 'Notify me when new feedback or performance reports are available.',
      initialChecked: true,
    },
    {
      title: 'Platform Tips',
      description: 'Receive tips and best practices to get the most out of MockDay.',
      initialChecked: false,
    },
  ];

  return (
    <div className="bg-card p-6 sm:p-8 rounded-lg shadow-sm">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-card-foreground">Notifications</h1>
        <p className="text-muted-foreground mt-1">Manage how you receive notifications from MockDay.</p>
      </div>

      <div>
        {notificationSettings.map((setting) => (
          <NotificationSetting key={setting.title} {...setting} />
        ))}
      </div>

      <div className="mt-8 flex justify-end">
          <Button>Save Preferences</Button>
      </div>
    </div>
  );
};

export default NotificationsPage;
