import { useState } from 'react';
import { useSelector } from 'react-redux';

import { RootState } from '../../redux/store';
import HobitProfile from './HobitProfile';
import { saveProfile, ProfileData } from '../../api/query';

const FIELD_OPTIONS: Record<string, { label_ko: string; label_en: string; options_ko: string[]; options_en: string[] }> = {
  department: {
    label_ko: '학과',
    label_en: 'Department',
    options_ko: ['컴퓨터학과', '데이터과학과', '인공지능학과'],
    options_en: ['Computer Science', 'Data Science', 'Artificial Intelligence'],
  },
  major_type: {
    label_ko: '전공 유형',
    label_en: 'Major Type',
    options_ko: ['심화전공', '이중전공', '복수전공', '부전공'],
    options_en: ['Intensive Major', 'Double Major', 'Multiple Major', 'Minor'],
  },
  grade: {
    label_ko: '학년',
    label_en: 'Grade',
    options_ko: ['1학년', '2학년', '3학년', '4학년'],
    options_en: ['1st year', '2nd year', '3rd year', '4th year'],
  },
  admission_year: {
    label_ko: '학번',
    label_en: 'Admission Year',
    options_ko: ['20학번', '21학번', '22학번', '23학번', '24학번', '25학번', '26학번'],
    options_en: ['Class of 2020', 'Class of 2021', 'Class of 2022', 'Class of 2023', 'Class of 2024', 'Class of 2025', 'Class of 2026'],
  },
  student_status: {
    label_ko: '학적 상태',
    label_en: 'Student Status',
    options_ko: ['재학', '편입', '휴학', '수료'],
    options_en: ['Enrolled', 'Transfer', 'Leave of Absence', 'Completed'],
  },
};

interface ProfileInputProps {
  missingFields: string[];
  onSaved: () => void;
}

const ProfileInput: React.FC<ProfileInputProps> = ({ missingFields, onSaved }) => {
  const isKorean = useSelector((state: RootState) => state.language.isKorean);
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const allSelected = missingFields.every((f) => selections[f]);

  const handleSelect = (field: string, value: string) => {
    setSelections((prev) => ({ ...prev, [field]: value }));
  };

  const handleConfirm = async () => {
    if (!allSelected || saving) return;
    setSaving(true);
    try {
      const profileData: ProfileData = { language: isKorean ? 'ko' : 'en' };
      if (selections.department) profileData.department = selections.department;
      if (selections.major_type) profileData.major_type = selections.major_type;
      if (selections.grade) profileData.grade = parseInt(selections.grade);
      if (selections.admission_year) profileData.admission_year = parseInt(selections.admission_year);
      if (selections.student_status) profileData.student_status = selections.student_status;
      await saveProfile(profileData);
      onSaved();
    } catch (err) {
      console.error('프로필 저장 실패:', err);
      setSaving(false);
    }
  };

  return (
    <div>
      <HobitProfile />
      <div className="bg-gray-100 w-full max-w-[330px] md:max-w-none md:w-[350px] h-auto mt-[20px] rounded-[20px] p-[20px]">
        <p className="text-[#686D76] font-6semibold text-sm md:text-base mb-[12px]">
          {isKorean
            ? '정확한 답변을 위해 아래 정보를 알려주세요.'
            : 'Please provide the following information for a more accurate answer.'}
        </p>

        {missingFields.map((field) => {
          const meta = FIELD_OPTIONS[field];
          if (!meta) return null;
          const label = isKorean ? meta.label_ko : meta.label_en;
          const options = isKorean ? meta.options_ko : meta.options_en;

          return (
            <div key={field} className="mb-[10px]">
              <p className="text-[#686D76] text-xs md:text-sm mb-[6px]">{label}</p>
              <div className="flex flex-wrap gap-[6px]">
                {options.map((opt) => {
                  const idx = options.indexOf(opt);
                  const storedValue =
                    field === 'grade' ? String(idx + 1) :
                    field === 'admission_year' ? String(20 + idx) :
                    opt;
                  const isSelected = selections[field] === storedValue;
                  return (
                    <button
                      key={opt}
                      onClick={() => handleSelect(field, storedValue)}
                      className={`px-[10px] py-[4px] rounded-full text-xs md:text-sm border transition-colors ${
                        isSelected
                          ? 'bg-[#686D76] text-white border-[#686D76]'
                          : 'bg-white text-[#686D76] border-[#686D76] hover:bg-gray-200'
                      }`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}

        <button
          onClick={handleConfirm}
          disabled={!allSelected || saving}
          className={`mt-[14px] w-full py-[8px] rounded-[10px] text-sm md:text-base font-6semibold transition-colors ${
            allSelected && !saving
              ? 'bg-[#686D76] text-white hover:bg-[#454952]'
              : 'bg-gray-300 text-gray-400 cursor-not-allowed'
          }`}
        >
          {saving
            ? isKorean ? '저장 중...' : 'Saving...'
            : isKorean ? '확인' : 'Confirm'}
        </button>
      </div>
    </div>
  );
};

export default ProfileInput;
