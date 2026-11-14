import {
  Building2,
  Droplets,
  Layers3,
  MapPinned,
} from "lucide-react";

const suggestions = [
  {
    id: "land-cover",
    label: "Analyze land cover",
    query: "Analyze the land cover in this image.",
    icon: Layers3,
  },
  {
    id: "buildings",
    label: "Count buildings",
    query: "How many buildings are visible in this image?",
    icon: Building2,
  },
  {
    id: "water",
    label: "Find water",
    query: "Identify the water-covered areas in this image.",
    icon: Droplets,
  },
  {
    id: "spatial",
    label: "Analyze a region",
    query: "What is visible in the center of the image?",
    icon: MapPinned,
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