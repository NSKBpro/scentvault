import { SafeAreaProvider } from 'react-native-safe-area-context';
import { ThemeProvider } from './src/theme';
import { RootNavigator } from './src/navigation';
import { Toaster } from './src/components/Toaster';

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <RootNavigator />
        <Toaster />
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
