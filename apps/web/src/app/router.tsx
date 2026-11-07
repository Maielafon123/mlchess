import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { AiPage, CoachPage, FriendPage, HomePage, LearnPage, MatchmakingPage, PlayPage, ReportPage } from "./pages";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "play", element: <PlayPage /> },
      { path: "play/ai", element: <AiPage /> },
      { path: "play/coach", element: <CoachPage /> },
      { path: "play/report", element: <ReportPage /> },
      { path: "play/friend", element: <FriendPage /> },
      { path: "play/matchmaking", element: <MatchmakingPage /> },
      { path: "learn", element: <LearnPage /> },
    ],
  },
]);
