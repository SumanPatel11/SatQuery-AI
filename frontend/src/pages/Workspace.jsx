import Sidebar from "../components/layout/Sidebar";
import TopBar from "../components/layout/TopBar";
import WorkspaceLayout from "../components/layout/Workspace";

function Workspace() {
  return (
    <div className="app-shell">
      <Sidebar />

      <main className="app-main">
        <TopBar />
        <WorkspaceLayout />
      </main>
    </div>
  );
}

export default Workspace;