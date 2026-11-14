import { forwardRef } from "react";

const Button = forwardRef(function Button(
  {
    children,
    variant = "primary",
    size = "md",
    icon: Icon = null,
    iconPosition = "left",
    loading = false,
    disabled = false,
    className = "",
    type = "button",
    ...props
  },
  ref
) {
  const classes = [
    "sq-button",
    `sq-button-${variant}`,
    `sq-button-${size}`,
    loading ? "is-loading" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="sq-button-loader" aria-hidden="true" />
      ) : (
        <>
          {Icon && iconPosition === "left" && (
            <Icon
              className="sq-button-icon"
              size={15}
              strokeWidth={1.8}
            />
          )}

          <span className="sq-button-content">
            {children}
          </span>

          {Icon && iconPosition === "right" && (
            <Icon
              className="sq-button-icon"
              size={15}
              strokeWidth={1.8}
            />
          )}
        </>
      )}
    </button>
  );
});

export default Button;