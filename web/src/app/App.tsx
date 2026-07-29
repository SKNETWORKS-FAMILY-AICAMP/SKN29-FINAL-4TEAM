import AppProviders from "./providers/AppProviders";
import AppRouter from "./router/AppRouter";

export default function App() {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  );
}
