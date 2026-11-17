import Sidebar from "../components/layout/Sidebar";
import TopBar from "../components/layout/TopBar";
import WorkspaceLayout from "../components/layout/Workspace";
import Analytics from "./Analytics";
import History from "./History";
import Images from "./Images";
import Queries from "./Queries";
import SettingsPage from "./Settings";
import { useSessionContext } from "../context/SessionContext";

function Workspace() {
  const { currentWorkspace } = useSessionContext();
  const currentPage = {
    "New Scan": <WorkspaceLayout />,
    Images: <Images />,
    Queries: <Queries />,
    Analytics: <Analytics />,
    History: <History />,
    Settings: <SettingsPage />,
  }[currentWorkspace] || <WorkspaceLayout />;

  return (
    <div className="app-shell">
      <Sidebar />

      <main className="app-main">
        <TopBar />
        {currentPage}
      </main>
    </div>
  );
}

export default Workspace;
