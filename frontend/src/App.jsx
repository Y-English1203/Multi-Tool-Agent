import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import AgentPanel from "./components/AgentPanel";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import KnowledgePage from "./pages/KnowledgePage";
import AnalyticsPage from "./pages/AnalyticsPage";
import TicketsPage from "./pages/TicketsPage";
import SettingsPage from "./pages/SettingsPage";
import { api } from "./lib/api";

const SESSIONS_KEY = "mta.sessions.v3";
const USER_KEY = "mta.user_id";
const PAGE_KEY = "mta.page";

const PAGES = ["dashboard", "chat", "knowledge", "analytics", "tickets", "settings"];

function readInitialPage() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (PAGES.includes(hash)) return hash;
  const stored = localStorage.getItem(PAGE_KEY);
  return PAGES.includes(stored) ? stored : "dashboard";
}

function makeId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function makeSession() {
  const now = new Date().toISOString();
  return {
    id: makeId(),
    session_id: makeId(),
    title: "新对话",
    messages: [],
    createdAt: now,
    updatedAt: now,
    lastTool: "",
    requestStatus: "idle",
  };
}

function normalizeSession(session) {
  return {
    ...session,
    id: session.id || makeId(),
    session_id: session.session_id || session.id || makeId(),
    title: session.title || "新对话",
    messages: Array.isArray(session.messages) ? session.messages : [],
    createdAt: session.createdAt || new Date().toISOString(),
    updatedAt: session.updatedAt || new Date().toISOString(),
    lastTool: session.lastTool || "",
    requestStatus: session.requestStatus || "idle",
  };
}

function loadSessions() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (Array.isArray(parsed) && parsed.length) {
      return parsed.map(normalizeSession);
    }
  } catch (error) {
    console.warn("读取本地会话失败：", error);
  }
  return [makeSession()];
}

function loadUser() {
  const stored = localStorage.getItem(USER_KEY);
  return stored && stored.trim() ? stored.trim() : "default_user";
}

export default function App() {
  const [sessions, setSessions] = useState(loadSessions);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [page, setPage] = useState(readInitialPage);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState(loadUser);
  const [health, setHealth] = useState(null);
  const [pendingQuestion, setPendingQuestion] = useState("");

  const sessionsRef = useRef(sessions);
  const activeSessionRef = useRef(activeSessionId);

  const effectiveSessionId = activeSessionId || sessions[0]?.id || "";
  const activeSession =
    sessions.find((session) => session.id === effectiveSessionId) || sessions[0] || null;

  useEffect(() => {
    if (!activeSessionId && sessions.length) {
      setActiveSessionId(sessions[0].id);
    }
  }, [activeSessionId, sessions]);

  useEffect(() => {
    sessionsRef.current = sessions;
    try {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.warn("保存本地会话失败：", error);
    }
  }, [sessions]);

  useEffect(() => {
    activeSessionRef.current = effectiveSessionId;
  }, [effectiveSessionId]);

  useEffect(() => {
    localStorage.setItem(PAGE_KEY, page);
    const target = `#/${page}`;
    if (window.location.hash !== target) {
      window.history.replaceState(null, "", target);
    }
  }, [page]);

  useEffect(() => {
    function handleHashChange() {
      const hash = window.location.hash.replace(/^#\/?/, "");
      if (PAGES.includes(hash)) setPage(hash);
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    localStorage.setItem(USER_KEY, user);
  }, [user]);

  useEffect(() => {
    let alive = true;
    async function loadHealth() {
      try {
        const data = await api.health();
        if (alive) setHealth(data);
      } catch {
        if (alive) setHealth({ status: "offline", version: "2.0.0", components: {} });
      }
    }
    loadHealth();
    const timer = setInterval(loadHealth, 60000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const updateSession = useCallback((sessionId, updater) => {
    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId
          ? normalizeSession(
              typeof updater === "function" ? updater(session) : { ...session, ...updater }
            )
          : session
      )
    );
  }, []);

  function createNewChat() {
    const session = makeSession();
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.id);
    activeSessionRef.current = session.id;
    setPage("chat");
    setPendingQuestion("");
    setMobileOpen(false);
  }

  function selectSession(sessionId) {
    setActiveSessionId(sessionId);
    activeSessionRef.current = sessionId;
    setPage("chat");
    setPendingQuestion("");
    setMobileOpen(false);
  }

  function deleteSession(sessionId) {
    const target = sessionsRef.current.find((session) => session.id === sessionId);
    const remaining = sessionsRef.current.filter((session) => session.id !== sessionId);

    if (target?.session_id) {
      api.deleteSession(target.session_id, user).catch(() => {});
    }

    if (!remaining.length) {
      const fresh = makeSession();
      setSessions([fresh]);
      setActiveSessionId(fresh.id);
      activeSessionRef.current = fresh.id;
      return;
    }

    setSessions(remaining);
    if (effectiveSessionId === sessionId) {
      setActiveSessionId(remaining[0].id);
      activeSessionRef.current = remaining[0].id;
    }
  }

  function clearSession(sessionId) {
    const target = sessionsRef.current.find((session) => session.id === sessionId);
    if (!target) return;
    if (target.session_id) {
      api.deleteSession(target.session_id, user).catch(() => {});
    }
    updateSession(sessionId, (session) => ({
      ...session,
      title: "新对话",
      messages: [],
      lastTool: "",
      requestStatus: "idle",
      updatedAt: new Date().toISOString(),
    }));
  }

  function clearAllLocalChat() {
    if (!window.confirm("确定清空浏览器中保存的全部对话吗？")) return;
    const fresh = makeSession();
    setSessions([fresh]);
    setActiveSessionId(fresh.id);
    activeSessionRef.current = fresh.id;
    setPendingQuestion("");
  }

  function navigate(nextPage, question) {
    setPage(nextPage);
    setMobileOpen(false);
    if (nextPage === "chat" && question) {
      setPendingQuestion(question);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#f7f8fc] text-slate-800">
      <Sidebar
        page={page}
        onNavigate={navigate}
        sessions={sessions}
        activeSessionId={activeSession?.id}
        onNewChat={createNewChat}
        onSelectSession={selectSession}
        onDeleteSession={deleteSession}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((value) => !value)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        health={health}
      />

      <div className="flex min-w-0 flex-1">
        {page === "dashboard" && (
          <DashboardPage
            onNavigate={navigate}
            onOpenMenu={() => setMobileOpen(true)}
            health={health}
            userId={user}
          />
        )}

        {page === "chat" && (
          <ChatPage
            key={activeSession?.id || "empty"}
            session={activeSession}
            userId={user}
            onUpdateSession={updateSession}
            initialQuestion={pendingQuestion}
            onConsumeInitialQuestion={() => setPendingQuestion("")}
            onOpenMenu={() => setMobileOpen(true)}
            onClearSession={clearSession}
            health={health}
          />
        )}

        {page === "knowledge" && (
          <KnowledgePage
            onOpenMenu={() => setMobileOpen(true)}
            onNavigate={navigate}
          />
        )}

        {page === "analytics" && (
          <AnalyticsPage
            onNavigate={navigate}
            onOpenMenu={() => setMobileOpen(true)}
          />
        )}

        {page === "tickets" && (
          <TicketsPage userId={user} onOpenMenu={() => setMobileOpen(true)} />
        )}

        {page === "settings" && (
          <SettingsPage
            user={user}
            onUserChange={setUser}
            onOpenMenu={() => setMobileOpen(true)}
            onClearLocalChat={clearAllLocalChat}
            health={health}
            onHealthChange={setHealth}
          />
        )}

        {page === "chat" && (
          <AgentPanel
            sending={activeSession?.requestStatus === "running"}
            lastTool={activeSession?.lastTool || ""}
            requestStatus={activeSession?.requestStatus || "idle"}
            session={activeSession}
            health={health}
          />
        )}
      </div>
    </div>
  );
}
