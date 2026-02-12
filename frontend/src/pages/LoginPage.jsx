import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../App";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { Scissors, Lock, User } from "lucide-react";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/";

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  if (isAuthenticated) {
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await login(username, password);
      toast.success("Welcome back!");
      navigate(from, { replace: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center p-4 relative"
      style={{
        backgroundImage: `linear-gradient(to bottom, rgba(9, 9, 11, 0.85), rgba(9, 9, 11, 0.95)), url('https://images.unsplash.com/photo-1768938896401-fe52fd18d3af?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwxfHxiYXJiZXIlMjBzaG9wJTIwaW50ZXJpb3IlMjBkYXJrJTIwYWVzdGhldGljfGVufDB8fHx8MTc3MDQwNDUwM3ww&ixlib=rb-4.1.0&w=1920&q=60&fm=webp')`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }}
    >
      <Card className="w-full max-w-md bg-card/95 backdrop-blur-sm border-border">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
            <Scissors className="w-8 h-8 text-primary" />
          </div>
          <div>
            <CardTitle className="font-heading text-3xl font-bold tracking-tight">
              Barbershop Autopilot
            </CardTitle>
            <CardDescription className="text-muted-foreground mt-2">
              Sign in to manage your shop
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="username"
                  data-testid="login-username-input"
                  type="text"
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-10 bg-input/50 border-input focus:ring-primary focus:border-primary"
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="password"
                  data-testid="login-password-input"
                  type="password"
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 bg-input/50 border-input focus:ring-primary focus:border-primary"
                  required
                />
              </div>
            </div>
            <Button
              type="submit"
              data-testid="login-submit-button"
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-medium"
              disabled={loading}
            >
              {loading ? "Signing in..." : "Sign In"}
            </Button>
          </form>
          {process.env.NODE_ENV === "development" && (
            <p className="text-xs text-muted-foreground text-center mt-6">
              Default credentials: admin / admin123
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
