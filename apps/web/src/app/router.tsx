import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { AiPage, CoachPage, HomePage, LearnPage, PlayPage, ReportPage } from "./pages";

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
      { path: "learn", element: <LearnPage /> },
    ],
  },
]);
