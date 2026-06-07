import { Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AppShell } from '@/components/AppShell';
import DashboardPage from '@/pages/DashboardPage';
import ExercisesPage from '@/pages/ExercisesPage';
import ProgressPage from '@/pages/ProgressPage';
import ExercisePage from '@/pages/ExercisePage';
import NotFoundPage from '@/pages/NotFoundPage';

function App() {
  return (
    <>
      <AppShell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/exercises" element={<ExercisesPage />} />
          <Route path="/exercise/:id" element={<ExercisePage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AppShell>
      <Toaster position="bottom-right" richColors />
    </>
  );
}

export default App;
