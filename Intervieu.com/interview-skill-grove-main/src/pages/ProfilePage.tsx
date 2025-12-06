
import React from 'react';
import ProfileDetails from '../components/profile/ProfileDetails'; // Import the new reusable component

const ProfilePage: React.FC = () => {
  // Now, this page simply renders the detailed, reusable profile component.
  // This ensures consistency with the Dashboard's profile tab and makes
  // the codebase much more maintainable.
  return (
    <ProfileDetails />
  );
};

export default ProfilePage;
