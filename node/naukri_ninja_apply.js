const fs = require('fs');
const path = require('path');
const { login, getUserProfile, manageProfiles, getPreferences } = require('naukri-ninja/utils/userUtils');
const { findNewJobs, applyForJobs, getExistingJobs, filterJobs } = require('naukri-ninja/utils/jobUtils');
const { localStorage } = require('naukri-ninja/utils/helper');
const { writeToFile } = require('naukri-ninja/utils/ioUtils');

const PROFILE_DATA_FILE = path.join(__dirname, 'naukri_ninja_profile.json');

async function loadLocalProfile() {
  if (!fs.existsSync(PROFILE_DATA_FILE)) {
    return null;
  }
  const raw = fs.readFileSync(PROFILE_DATA_FILE, 'utf8');
  return JSON.parse(raw);
}

async function saveLocalProfile(profile) {
  fs.writeFileSync(PROFILE_DATA_FILE, JSON.stringify(profile, null, 2), 'utf8');
}

async function initialize() {
  let profile = await loadLocalProfile();
  if (!profile) {
    console.log('No local profile found. Please login interactively first.');
    return null;
  }

  localStorage.clear();
  localStorage.setItem('profile', profile.user);
  localStorage.setItem('preferences', profile.preferences);
  localStorage.setItem('authorization', profile.authorization);

  return profile;
}

async function loginAndSave(email, password) {
  const profile = { creds: { username: email, password } };
  const loginInfo = await login(profile);
  const auth = loginInfo.authorization;
  localStorage.setItem('authorization', auth);

  const user = await getUserProfile();
  localStorage.setItem('profile', user);

  const preferences = await getPreferences(user);
  localStorage.setItem('preferences', preferences);

  const profiles = await manageProfiles(user, loginInfo);
  writeToFile(profiles, 'profiles');

  const saved = {
    authorization: auth,
    user,
    preferences,
    profiles,
  };
  saveLocalProfile(saved);
  console.log('Saved local profile and preferences.');
  return saved;
}

async function runApply(options = {}) {
  const profile = await initialize();
  if (!profile) {
    return;
  }

  const preferences = profile.preferences;
  const pages = options.pages ?? preferences.noOfPages ?? 3;
  const useExisting = options.useExisting ?? false;
  const jobs = useExisting ? await getExistingJobs() : await findNewJobs(pages, 1);

  if (!jobs || jobs.length === 0) {
    console.log('No jobs found to apply.');
    return;
  }

  console.log(`Applying to ${jobs.length} jobs...`);
  const result = await applyForJobs(jobs);
  if (result?.jobs) {
    console.log(`Applied to ${result.jobs.length} jobs.`);
  } else {
    console.log('No jobs were applied.');
  }
}

async function main() {
  const rawArgs = process.argv.slice(2);
  const args = rawArgs
    .map((a) => (typeof a === 'string' ? a.trim() : a))
    .map((a) => (typeof a === 'string' ? a.replace(/^"|"$/g, '') : a))
    .map((a) => (typeof a === 'string' ? a.replace(/,+$/, '') : a))
    .filter((a) => a !== null && a !== undefined && a !== '');
  const cmd = args[0] ? String(args[0]).toLowerCase() : '';
  console.log('Arguments:', args, 'cmd:', cmd);

  if (cmd === 'login') {
    const email = args[1];
    const password = args[2];
    console.log('Email:', email, 'Password:', password);
    if (!email || !password) {
      console.error('Usage: node naukri_ninja_apply.js login <email> <password>');
      process.exit(1);
    }
    await loginAndSave(email, password);
    return;
  }

  await runApply();
}

main().catch((error) => {
  console.error('Error:', error?.message || error);
  process.exit(1);
});
