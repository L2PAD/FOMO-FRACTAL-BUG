// Legacy alias — kept for screens importing `{ theme }` directly.
// Maps to the new darkTheme from themes.ts. For live theme switching
// always prefer `useColors()` + `makeStyles(colors)` pattern.
import { darkTheme } from './themes';

export const theme = {
  colors: darkTheme.colors,
  spacing: darkTheme.spacing,
  radius: darkTheme.radius,
  fontSize: darkTheme.fontSize,
  fontWeight: darkTheme.fontWeight,
};
