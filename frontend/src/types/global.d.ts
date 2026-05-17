// Extend window for global variables
interface Window {
  EMERGENT_ENV?: string;
}

// Module declarations for JSX components (shadcn)
declare module '@/components/ui/*' {
  const Component: React.FC<any>;
  export default Component;
  export const Badge: React.FC<any>;
  export const Button: React.FC<any>;
  export const Card: React.FC<any>;
  export const CardHeader: React.FC<any>;
  export const CardContent: React.FC<any>;
  export const CardTitle: React.FC<any>;
  export const CardDescription: React.FC<any>;
  export const CardFooter: React.FC<any>;
}

// Make all .jsx imports work without issues
declare module '*.jsx' {
  const Component: React.FC<any>;
  export default Component;
}
