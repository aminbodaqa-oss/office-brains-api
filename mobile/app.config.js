// Keep Firebase's client configuration in EAS as a protected file variable,
// rather than committing google-services.json to the public repository.
module.exports = ({ config }) => {
  const googleServicesFile = process.env.GOOGLE_SERVICES_JSON;

  if (process.env.EAS_BUILD && !googleServicesFile) {
    throw new Error(
      "Missing GOOGLE_SERVICES_JSON. Add google-services.json as an EAS file environment variable for the preview environment."
    );
  }

  return {
    ...config,
    android: {
      ...config.android,
      ...(googleServicesFile ? { googleServicesFile } : {}),
    },
  };
};
