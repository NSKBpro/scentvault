import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { colors } from '../theme/colors';
import { HomeScreen } from '../screens/Home';
import { CollectionScreen } from '../screens/Collection';
import { AddFragranceScreen } from '../screens/AddFragrance';
import { DiscoverScreen } from '../screens/Discover';
import { FragranceDetailScreen } from '../screens/FragranceDetail';
import { DealsScreen } from '../screens/Deals';
import { DiaryScreen } from '../screens/Diary';
import { ProfileScreen } from '../screens/Profile';

const screenOptions = {
  headerStyle: { backgroundColor: colors.background },
  headerTintColor: colors.text,
  headerTitleStyle: { fontFamily: 'DMSans_500Medium' },
  headerShadowVisible: false,
  contentStyle: { backgroundColor: colors.background },
};

const HomeStackNav = createNativeStackNavigator();
const CollectionStackNav = createNativeStackNavigator();
const DiaryStackNav = createNativeStackNavigator();
const DiscoverStackNav = createNativeStackNavigator();
const DealsStackNav = createNativeStackNavigator();

const detail = { title: 'Details' };

export function HomeStack() {
  return (
    <HomeStackNav.Navigator screenOptions={screenOptions}>
      <HomeStackNav.Screen name="HomeMain" component={HomeScreen} options={{ headerShown: false }} />
      <HomeStackNav.Screen name="FragranceDetail" component={FragranceDetailScreen} options={detail} />
      <HomeStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile & settings' }} />
    </HomeStackNav.Navigator>
  );
}

export function CollectionStack() {
  return (
    <CollectionStackNav.Navigator screenOptions={screenOptions}>
      <CollectionStackNav.Screen name="CollectionMain" component={CollectionScreen} options={{ headerShown: false }} />
      <CollectionStackNav.Screen name="FragranceDetail" component={FragranceDetailScreen} options={detail} />
      <CollectionStackNav.Screen name="AddFragrance" component={AddFragranceScreen} options={{ title: 'Add fragrance' }} />
    </CollectionStackNav.Navigator>
  );
}

export function DiaryStack() {
  return (
    <DiaryStackNav.Navigator screenOptions={screenOptions}>
      <DiaryStackNav.Screen name="DiaryMain" component={DiaryScreen} options={{ headerShown: false }} />
      <DiaryStackNav.Screen name="FragranceDetail" component={FragranceDetailScreen} options={detail} />
    </DiaryStackNav.Navigator>
  );
}

export function DiscoverStack() {
  return (
    <DiscoverStackNav.Navigator screenOptions={screenOptions}>
      <DiscoverStackNav.Screen name="DiscoverMain" component={DiscoverScreen} options={{ headerShown: false }} />
      <DiscoverStackNav.Screen name="FragranceDetail" component={FragranceDetailScreen} options={detail} />
      <DiscoverStackNav.Screen name="AddFragrance" component={AddFragranceScreen} options={{ title: 'Add fragrance' }} />
    </DiscoverStackNav.Navigator>
  );
}

export function DealsStack() {
  return (
    <DealsStackNav.Navigator screenOptions={screenOptions}>
      <DealsStackNav.Screen name="DealsMain" component={DealsScreen} options={{ headerShown: false }} />
      <DealsStackNav.Screen name="FragranceDetail" component={FragranceDetailScreen} options={detail} />
      <DealsStackNav.Screen name="AddFragrance" component={AddFragranceScreen} options={{ title: 'Add fragrance' }} />
    </DealsStackNav.Navigator>
  );
}
