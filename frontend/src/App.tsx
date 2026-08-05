import { Routes, Route } from "react-router-dom";
import { LiveRunPage } from "./pages/LiveRunPage";
import { EvalLeaderboardPage } from "./pages/EvalLeaderboardPage";
import { BugDetailPage } from "./pages/BugDetailPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LiveRunPage />} />
      <Route path="/leaderboard" element={<EvalLeaderboardPage />} />
      <Route path="/bugs/:bugId" element={<BugDetailPage />} />
    </Routes>
  );
}
