import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { HomePage, LearnPage, PlayPage } from "./pages";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "play", element: <PlayPage /> },
      { path: "learn", element: <LearnPage /> },
    ],
  },
]);
