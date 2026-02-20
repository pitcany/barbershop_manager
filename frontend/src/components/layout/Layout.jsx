import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../App";
import { Button } from "../ui/button";
import {
  LayoutDashboard,
  MessageSquare,
  Calendar,
  Users,
  UserRound,
  Settings,
  LogOut,
  Scissors,
  Menu,
  X,
  User,
  Wrench,
  BarChart,
  Shield
} from "lucide-react";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/appointments", label: "Appointments", icon: Calendar },
  { path: "/clients", label: "Clients", icon: User },
  { path: "/conversations", label: "Conversations", icon: MessageSquare },
  { path: "/waitlist", label: "Waitlist", icon: Users },
  { path: "/manage", label: "Manage Shop", icon: Wrench },
  { path: "/reporting", label: "Reporting", icon: BarChart },
  { path: "/jobs", label: "Jobs", icon: Settings },
  { path: "/settings", label: "Settings", icon: Scissors },
];

const superAdminItem = { path: "/admin", label: "Platform Admin", icon: Shield };

export default function Layout({ children, title }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:sticky top-0 left-0 z-50 h-screen w-64 
        bg-card border-r border-border
        transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                <Scissors className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h1 className="font-heading font-semibold text-lg">Autopilot</h1>
                <p className="text-xs text-muted-foreground">Barbershop Manager</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 py-4">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => `
                  flex items-center gap-3 px-6 py-3 text-sm font-medium
                  transition-colors duration-200
                  ${isActive 
                    ? 'bg-primary/10 text-primary border-r-2 border-primary' 
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                  }
                `}
                data-testid={`nav-${item.label.toLowerCase()}`}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{user?.username || "Admin"}</p>
                <p className="text-xs text-muted-foreground">Shop Manager</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                data-testid="logout-button"
                className="text-muted-foreground hover:text-foreground"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-h-screen">
        {/* Mobile header */}
        <header className="lg:hidden sticky top-0 z-30 bg-background/95 backdrop-blur border-b border-border p-4">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              data-testid="mobile-menu-button"
            >
              <Menu className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-2">
              <Scissors className="w-5 h-5 text-primary" />
              <span className="font-heading font-semibold">Autopilot</span>
            </div>
            <div className="w-10" />
          </div>
        </header>

        {/* Page content */}
        <div className="p-6 lg:p-8">
          {title && (
            <h1 className="font-heading text-3xl font-bold tracking-tight mb-8" data-testid="page-title">
              {title}
            </h1>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}
