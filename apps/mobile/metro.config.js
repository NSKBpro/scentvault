// Lets the app import the generated API types from packages/api-types (monorepo).
const path = require('path');
const { getDefaultConfig } = require('expo/metro-config');

const root = path.resolve(__dirname, '../..');
const config = getDefaultConfig(__dirname);
config.watchFolders = [path.join(root, 'packages')];
config.resolver.extraNodeModules = {
  ...(config.resolver.extraNodeModules || {}),
  '@api-types': path.join(root, 'packages/api-types'),
};
module.exports = config;
