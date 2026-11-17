import { ArrowUp, Paperclip, Sparkles } from "lucide-react";
import { useState } from "react";

const suggestions = [
  "How many buildings are visible?",
  "Segment land-cover classes and report pixel counts.",
];

function QueryInput({ onSubmit, disabled = false }) {
  const [query, setQuery] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery || disabled || !onSubmit) return;

    const result = await onSubmit(trimmedQuery);

    if (result !== false) {
      setQuery("");
    }
  };

  return (
    <section className="query-area">
      <div className="query-header">
        <div className="query-title">
          <span className="query-title-icon">
            <Sparkles size={13} strokeWidth={1.7} />
          </span>

          <span>ASK SATQUERY AI</span>
        </div>

        <span className="query-mode">
          Natural-language analysis
        </span>
      </div>

      <form className="query-box" onSubmit={handleSubmit}>
        <button
          type="button"
          className="query-attachment"
          aria-label="Image upload is available in the viewer"
          title="Upload imagery using the image viewer"
          disabled
        >
          <Paperclip size={16} strokeWidth={1.7} />
        </button>

        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask about buildings, roads, vegetation, water, or changes..."
          aria-label="Ask SatQuery AI"
          disabled={disabled}
        />

        <button
          type="submit"
          className="query-submit"
          disabled={!query.trim() || disabled}
          aria-label="Submit query"
          title="Submit query"
        >
          <ArrowUp size={16} strokeWidth={2} />
        </button>
      </form>

      <div className="query-suggestions">
        <span className="query-suggestions-label">
          TRY ASKING
        </span>

        <div className="query-suggestion-list">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={disabled}
              onClick={() => setQuery(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export default QueryInput;
