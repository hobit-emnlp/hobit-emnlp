import { useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import { FiRefreshCcw, FiUser } from 'react-icons/fi';

import { getProfile, resetProfile, ProfileData } from '../api/query';
import { RootState } from '../redux/store';

const hasProfile = (profile: ProfileData) =>
  Boolean(
    profile.department ||
      profile.admission_year ||
      profile.major_type ||
      profile.grade ||
      profile.student_status
  );

const ProfileBar: React.FC = () => {
  const isKorean = useSelector((state: RootState) => state.language.isKorean);
  const [profile, setProfile] = useState<ProfileData>({});
  const [loading, setLoading] = useState(false);

  const loadProfile = async () => {
    try {
      const data = await getProfile();
      setProfile(data.profile ?? {});
    } catch (err) {
      console.error('Error while loading profile:', err);
    }
  };

  useEffect(() => {
    loadProfile();
    const handler = () => loadProfile();
    window.addEventListener('hobit-profile-updated', handler);
    window.addEventListener('storage', handler);
    return () => {
      window.removeEventListener('hobit-profile-updated', handler);
      window.removeEventListener('storage', handler);
    };
  }, []);

  const label = useMemo(() => {
    if (!hasProfile(profile)) {
      return isKorean ? '프로필 미설정' : 'Profile not set';
    }

    const parts: string[] = [];
    if (profile.department) parts.push(profile.department);
    if (profile.admission_year) parts.push(`${profile.admission_year}학번`);
    if (profile.major_type) parts.push(profile.major_type);
    if (profile.grade) parts.push(`${profile.grade}학년`);
    if (profile.student_status) parts.push(profile.student_status);

    return `${isKorean ? '현재 기준' : 'Current profile'}: ${parts.join(' · ')}`;
  }, [isKorean, profile]);

  const handleReset = async () => {
    if (loading) return;
    setLoading(true);
    try {
      await resetProfile();
      setProfile({});
      window.dispatchEvent(new Event('hobit-profile-updated'));
      window.dispatchEvent(new Event('hobit-profile-reset'));
    } catch (err) {
      console.error('Error while resetting profile:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed top-[60px] md:top-[70px] left-0 right-0 z-40 bg-white/95 border-b border-gray-200 px-4 py-2 md:px-[20px]">
      <div className="flex items-center justify-between gap-3 max-w-[900px] mx-auto text-xs md:text-sm text-[#686D76]">
        <div className="flex min-w-0 items-center gap-2">
          <FiUser className="shrink-0 text-[#750E21]" />
          <span className="truncate">{label}</span>
        </div>
        <button
          type="button"
          onClick={handleReset}
          disabled={loading}
          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs md:text-sm hover:bg-gray-100 disabled:opacity-60"
          title={
            hasProfile(profile)
              ? isKorean ? '저장된 프로필과 대화 초기화' : 'Reset saved profile and chat'
              : isKorean ? '현재 대화 지우기' : 'Clear current chat'
          }
        >
          <FiRefreshCcw />
          <span>
            {hasProfile(profile)
              ? isKorean ? '초기화' : 'Reset'
              : isKorean ? '대화 지우기' : 'Clear'}
          </span>
        </button>
      </div>
    </div>
  );
};

export default ProfileBar;
