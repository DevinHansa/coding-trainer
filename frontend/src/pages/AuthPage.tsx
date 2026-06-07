import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/AuthContext';

const AuthPage: React.FC = () => {
  const { token, login, register, error, clearError } = useAuth();
  const navigate = useNavigate();

  // Form states
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  // Clear errors on tab change
  const handleTabChange = () => {
    clearError();
    setLocalError(null);
  };

  // If already logged in, redirect directly to dashboard
  if (token) {
    return <Navigate to="/" replace />;
  }

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!loginUsername || !loginPassword) {
      setLocalError('Please enter both username and password.');
      return;
    }
    setLoading(true);
    const success = await login(loginUsername, loginPassword);
    setLoading(false);
    if (success) {
      navigate('/');
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!regUsername || !regPassword || !regConfirmPassword) {
      setLocalError('All fields are required.');
      return;
    }
    if (regPassword.length < 6) {
      setLocalError('Password must be at least 6 characters.');
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setLocalError('Passwords do not match.');
      return;
    }
    setLoading(true);
    const success = await register(regUsername, regPassword);
    setLoading(false);
    if (success) {
      navigate('/');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-500/10 via-background to-pink-500/10 dark:from-indigo-950/20 dark:via-background dark:to-pink-950/20 p-4 relative overflow-hidden">
      {/* Decorative blurred circles for visual aesthetics */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl -z-10 animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl -z-10" />

      <div className="w-full max-w-md space-y-6 fade-in">
        {/* Brand Logo and Title */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-pink-500 text-primary-foreground font-bold text-xl shadow-lg shadow-primary/20">
            🎯
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">SDE Prep</h1>
          <p className="text-muted-foreground text-sm">
            Senior Data Engineer Practice & Adaptive Interview Platform
          </p>
        </div>

        {/* Auth Tabs */}
        <Tabs defaultValue="login" className="w-full" onValueChange={handleTabChange}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">Sign In</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>

          {/* Login Panel */}
          <TabsContent value="login">
            <Card className="border-muted/40 shadow-xl backdrop-blur-sm bg-card/90">
              <CardHeader>
                <CardTitle>Sign In</CardTitle>
                <CardDescription>
                  Enter your credentials to resume your data engineering practice.
                </CardDescription>
              </CardHeader>
              <form onSubmit={handleLoginSubmit}>
                <CardContent className="space-y-4">
                  {(error || localError) && (
                    <Alert variant="destructive">
                      <AlertDescription>
                        {localError || error}
                      </AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      placeholder="e.g. sde_coder"
                      value={loginUsername}
                      onChange={(e) => setLoginUsername(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                </CardContent>
                <CardFooter>
                  <Button type="submit" className="w-full font-medium" disabled={loading}>
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <span className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                        Signing in...
                      </span>
                    ) : (
                      'Sign In'
                    )}
                  </Button>
                </CardFooter>
              </form>
            </Card>
          </TabsContent>

          {/* Register Panel */}
          <TabsContent value="register">
            <Card className="border-muted/40 shadow-xl backdrop-blur-sm bg-card/90">
              <CardHeader>
                <CardTitle>Create Account</CardTitle>
                <CardDescription>
                  Start practicing SQL, Python, and PySpark under a private profile.
                </CardDescription>
              </CardHeader>
              <form onSubmit={handleRegisterSubmit}>
                <CardContent className="space-y-4">
                  {(error || localError) && (
                    <Alert variant="destructive">
                      <AlertDescription>
                        {localError || error}
                      </AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-2">
                    <Label htmlFor="reg-username">Username</Label>
                    <Input
                      id="reg-username"
                      placeholder="e.g. spark_master"
                      value={regUsername}
                      onChange={(e) => setRegUsername(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="reg-password">Password (min 6 chars)</Label>
                    <Input
                      id="reg-password"
                      type="password"
                      placeholder="••••••••"
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confirm-password">Confirm Password</Label>
                    <Input
                      id="confirm-password"
                      type="password"
                      placeholder="••••••••"
                      value={regConfirmPassword}
                      onChange={(e) => setRegConfirmPassword(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                </CardContent>
                <CardFooter>
                  <Button type="submit" className="w-full font-medium" disabled={loading}>
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <span className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                        Creating account...
                      </span>
                    ) : (
                      'Register'
                    )}
                  </Button>
                </CardFooter>
              </form>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Practice Tip Card at the bottom */}
        <div className="text-center text-xs text-muted-foreground bg-muted/40 border rounded-lg p-3">
          💡 <strong>Interview Tip:</strong> Practice PySpark data skew scenarios and SQL Window functions. They are the most common Senior Data Engineer topics!
        </div>
      </div>
    </div>
  );
};

export default AuthPage;
