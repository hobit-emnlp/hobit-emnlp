import React, { useEffect } from 'react';
import { AiFillHome } from 'react-icons/ai';
import { TbSend2 } from 'react-icons/tb';
import { useDispatch, useSelector } from 'react-redux';

import {
  sendInputValue,
  setIsEmpty,
  updateLiveValue,
} from '../redux/inputSlice';
import { setHomeClicked } from '../redux/homeSlice';
import { RootState } from '../redux/store';

const Input: React.FC = () => {
  const dispatch = useDispatch();
  const liveValue = useSelector((state: RootState) => state.input.liveValue);
  const isLoading = useSelector((state: RootState) => state.input.isLoading);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const isKorean = useSelector((state: RootState) => state.language.isKorean);
  const [isSending, setIsSending] = React.useState(false);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, [liveValue]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;

    dispatch(updateLiveValue(value));
    dispatch(setIsEmpty(value === ''));
  };

  const handleSend = () => {
    if (liveValue.trim() !== '' && !isSending && !isLoading) {
      setIsSending(true);
      dispatch(sendInputValue(liveValue));
      dispatch(updateLiveValue(''));
      dispatch(setIsEmpty(true));

      setTimeout(() => setIsSending(false), 500);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSend();
    }
  };

  const handleHomeClick = () => {
    dispatch(setHomeClicked());
  };

  return (
    <div className="bg-white border-t-2 fixed bottom-0 left-0 z-50 w-full h-[60px] md:h-[80px] flex items-center px-[15px] md:px-[20px]">
      <AiFillHome
        className="text-[28px] md:text-[32px] text-[#750E21] mr-[15px] md:mr-[20px] hover:text-gray-600 cursor-pointer"
        onClick={handleHomeClick}
      />
      <div className={`w-full h-[40px] md:h-[48px] px-4 rounded-[30px] flex flex-row items-center transition-colors ${isLoading ? 'bg-gray-100' : 'bg-gray-200'}`}>
        <input
          type="text"
          ref={inputRef}
          placeholder={
            isLoading
              ? (isKorean ? '답변 생성 중...' : 'Generating response...')
              : (isKorean ? '호빗에게 물어보세요!' : 'Ask Anything to HoBIT!')
          }
          value={liveValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          className="bg-transparent w-full outline-none placeholder-[#aaaaaa] font-6semibold text-base md:text-xl disabled:cursor-not-allowed"
        />
        <TbSend2
          onClick={handleSend}
          className={`ml-[10px] text-[20px] md:text-[24px] transition-colors ${isLoading ? 'text-[#dddddd] cursor-not-allowed' : 'text-[#aaaaaa] hover:text-[#000000] cursor-pointer'}`}
        />
      </div>
    </div>
  );
};

export default Input;
