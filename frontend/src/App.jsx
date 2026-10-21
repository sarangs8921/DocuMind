
import { useState } from "react";
import DocumentLibrary from "./components/DocumentLibrary";
import ChatWindow from "./components/ChatWindow";
import "./App.css";

function App() {
  const [selectedDocument, setSelectedDocument] = useState(null);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-mark">D</div>

        <div>
          <h1>DocuMind</h1>
          <p>Chat with your documents</p>
        </div>
      </header>

      <main className="app-main">
        <DocumentLibrary
          selectedDocument={selectedDocument}
          onSelectDocument={setSelectedDocument}
        />

        <ChatWindow document={selectedDocument} />
      </main>
    </div>
  );
}

export default App;
