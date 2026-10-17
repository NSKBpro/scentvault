import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing } from '../theme';
import { HomeStack, CollectionStack, DiaryStack, DiscoverStack, DealsStack } from './Stacks';

const Tab = createBottomTabNavigator();

const tabs = [
  { name: 'Home', icon: 'home-outline', iconActive: 'home', label: 'Home' },
  { name: 'Collection', icon: 'grid-outline', iconActive: 'grid', label: 'Collection' },
  { name: 'Diary', icon: 'calendar-outline', iconActive: 'calendar', label: 'Diary' },
  { name: 'Discover', icon: 'sparkles-outline', iconActive: 'sparkles', label: 'Discover' },
  { name: 'Deals', icon: 'pricetag-outline', iconActive: 'pricetag', label: 'Deals' },
] as const;

function CustomTabBar({ state, navigation }: any) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.tabBar, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
      {state.routes.map((route: any, index: number) => {
        const isFocused = state.index === index;
        const tab = tabs[index];
        return (
          <TouchableOpacity
            key={route.key}
            onPress={() => (isFocused ? navigation.navigate(route.name, { screen: undefined }) : navigation.navigate(route.name))}
            style={styles.tabItem}
            accessibilityRole="tab"
            accessibilityLabel={tab.label}
            accessibilityState={{ selected: isFocused }}
          >
            <Ionicons
              name={isFocused ? tab.iconActive : tab.icon}
              size={20}
              color={isFocused ? colors.tabActive : colors.tabInactive}
            />
            <Text style={[styles.tabLabel, { color: isFocused ? colors.tabActive : colors.tabInactive }]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

export function TabNavigator() {
  return (
    <Tab.Navigator tabBar={(props) => <CustomTabBar {...props} />} screenOptions={{ headerShown: false }}>
      <Tab.Screen name="Home" component={HomeStack} />
      <Tab.Screen name="Collection" component={CollectionStack} />
      <Tab.Screen name="Diary" component={DiaryStack} />
      <Tab.Screen name="Discover" component={DiscoverStack} />
      <Tab.Screen name="Deals" component={DealsStack} />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.tabBarBg,
    borderTopWidth: 1,
    borderTopColor: colors.separator,
    paddingTop: spacing.sm,
  },
  tabItem: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3 },
  tabLabel: { fontSize: 11, fontFamily: 'DMSans_500Medium' },
});