import { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Cpu, Settings, FileText,
  Menu, X, LogOut, UserCog,
} from 'lucide-react';
import { useLogout, useCurrentAdmin, ProfileDialog } from '@/features/auth';

const navItems = [
  { path: '/dashboard', label: '仪表盘', icon: LayoutDashboard },
  { path: '/agents', label: 'Agent 管理', icon: Users },
  { path: '/models', label: '模型配置', icon: Cpu },
  { path: '/system', label: '系统配置', icon: Settings },
  { path: '/logs', label: '操作日志', icon: FileText },
];

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const location = useLocation();
  const logout = useLogout();
  const { data: admin } = useCurrentAdmin();

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-60' : 'w-16'
        } bg-card border-r border-border transition-all duration-300 flex flex-col fixed h-full z-10`}
      >
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-border">
          {sidebarOpen && (
            <span className="font-bold text-lg truncate">Agent Manager</span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 rounded-md hover:bg-muted transition-colors"
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path ||
              (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <item.icon size={18} className="shrink-0" />
                {sidebarOpen && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Admin info */}
        {sidebarOpen && (
          <div className="p-3 border-t border-border">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{admin?.username || '管理员'}</p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setProfileDialogOpen(true)}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  title="账户资料"
                >
                  <UserCog size={16} />
                </button>
                <button
                  onClick={logout}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-destructive transition-colors"
                  title="登出"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </div>
          </div>
        )}
        {!sidebarOpen && (
          <div className="p-3 border-t border-border flex justify-center gap-1">
            <button
              onClick={() => setProfileDialogOpen(true)}
              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="账户资料"
            >
              <UserCog size={16} />
            </button>
            <button
              onClick={logout}
              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-destructive transition-colors"
              title="登出"
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className={`flex-1 ${sidebarOpen ? 'ml-60' : 'ml-16'} transition-all duration-300 overflow-auto`}>
        <div className="p-6">
          <Outlet />
        </div>
      </main>

      <ProfileDialog
        open={profileDialogOpen}
        onOpenChange={setProfileDialogOpen}
        currentAdmin={admin}
      />
    </div>
  );
}
