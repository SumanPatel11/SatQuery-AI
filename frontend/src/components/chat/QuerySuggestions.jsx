import {
  Building2,
  Clock3,
  Layers3,
  Waves,
} from "lucide-react";

const suggestions = [
  {
    id: "land-cover",
    label: "Land-cover pixel counts",
    query: "Segment the land-cover classes and report pixel counts.",
    icon: Layers3,
  },
  {
    id: "buildings",
    label: "Count buildings",
    query: "How many buildings are visible in this image?",
    icon: Building2,
  },
  {
    id: "flood",
    label: "Detect flooding",
    query: "Detect flooded areas in this image.",
    icon: Waves,
  },
  {
    id: "change",
    label: "Compare buildings",
    query: "Compare buildings before and after for changes.",
    icon: Clock3,
  },
];

function QuerySuggestions({
  onSelect,
  disabled = false,
}) {
  return (
    <div className="query-suggestions">
      <div className="query-suggestions-header">
        <span className="query-suggestions-kicker">
          TRY A QUERY
        </span>
      </div>

      <div className="query-suggestions-list">
        {suggestions.map((suggestion) => {
          const Icon = suggestion.icon;

          return (
            <button
              key={suggestion.id}
              type="button"
              className="query-suggestion"
              onClick={() =>
                onSelect?.(suggestion.query)
              }
              disabled={disabled}
            >
              <span className="query-suggestion-icon">
                <Icon
                  size={14}
                  strokeWidth={1.7}
                />
              </span>

              <span className="query-suggestion-text">
                {suggestion.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default QuerySuggestions;
