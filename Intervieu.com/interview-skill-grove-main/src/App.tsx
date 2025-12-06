
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/layouts/Layout";
import InterviewLayout from "./components/layouts/InterviewLayout";
import SettingsLayout from "./components/layouts/SettingsLayout";
import Index from "./pages/Index";
import Dashboard from "./pages/Dashboard";
import Interview from "./pages/Interview";
import Report from "./pages/Report";
import NotFound from "./pages/NotFound";
import LoginPage from "./pages/Login";
import SignupPage from "./pages/Signup";
import StartInterview from "./pages/StartInterview";
import ProfilePage from "./pages/ProfilePage";
import ProfileSetup from "./pages/ProfileSetup";
import NotificationsPage from "./pages/NotificationsPage";
import SecurityPage from "./pages/settings/SecurityPage";
import HardwareCheck from "./pages/HardwareCheck";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public routes with Layout */}
            <Route element={<Layout />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/" element={<Index />} />

              {/* Protected routes with Layout */}
              <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/start-interview" element={<StartInterview />} />
                <Route path="/hardware-check" element={<HardwareCheck />} />
                <Route path="/interviews/:interviewId/report" element={<Report />} />
                <Route path="/report" element={<Report />} /> {/* Legacy route with query params */}
                
                {/* Settings Section with its own nested layout */}
                <Route path="/profile" element={<SettingsLayout />}>
                  <Route index element={<ProfilePage />} />
                  <Route path="setup" element={<ProfileSetup />} />
                  <Route path="notifications" element={<NotificationsPage />} />
                  <Route path="security" element={<SecurityPage />} />
                </Route>
              </Route>

              <Route path="*" element={<NotFound />} />
            </Route>

            {/* Interview route - completely separate, no Layout/navigation */}
            <Route element={<ProtectedRoute />}>
              <Route element={<InterviewLayout />}>
                <Route path="/interview" element={<Interview />} />
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
