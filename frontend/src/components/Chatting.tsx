import { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import HelloHobit from './chat/HelloHobit';
import GeneralResponse from './chat/GeneralResponse';
import FAQResponse from './chat/FAQResponse';
import AllCategoriesResponse from './chat/AllCategoriesResponse';
import SeniorResponse from './chat/SeniorResponse';
import Query from './chat/Query';
import { RootState } from '../redux/store';
import { Faq } from '../types/faq';
import { sendQuestion, getAllQuestions, getFaqById } from '../api/query';
import { setQuestions } from '../redux/questionsSlice';
import { resetHomeClicked } from '../redux/homeSlice';
import { clearSent } from '../redux/inputSlice';
import GreetResponse from './chat/GreetResponse';
import ProfileInput from './chat/ProfileInput';
import { setId, setIsLoading } from '../redux/inputSlice';

interface ChatItem {
  query: string;
  response: Faq[];
  loading: boolean;
  flag: boolean;
  seniorMode: number;
  is_greet: boolean;
  is_able: boolean;
  is_freq: boolean;
  is_smalltalk: boolean;
  needs_profile: boolean;
  missing_fields: string[];
  initialSeniorFaqId?: number;
}

const Chatting: React.FC = () => {
  const dispatch = useDispatch();
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const sentValue = useSelector((state: RootState) => state.input.sentValue);
  const sent = useSelector((state: RootState) => state.input.sent);
  const directFaqId = useSelector((state: RootState) => state.input.directFaqId);
  const isKorean = useSelector((state: RootState) => state.language.isKorean);
  const homeClicked = useSelector((state: RootState) => state.home.homeClicked);
  const feedbackClicked = useSelector(
    (state: RootState) => state.feedback.feedbackClicked
  );
  const seniorFaqId = useSelector(
    (state: RootState) => state.seniorFaqId.seniorFaqId
  );

  const [chatHistory, setChatHistory] = useState<ChatItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const newChatItemRef = useRef<ChatItem | null>(null);

  const removeLastChatItem = () => {
    setChatHistory((prevHistory) => prevHistory.slice(0, -1));
  };

  useEffect(() => {
    const fetchAllQuestions = async () => {
      try {
        const response = await getAllQuestions();
        dispatch(setQuestions(response.questions));
      } catch (err) {
        console.error('Error while fetching all questions:', err);
        setError(err as string);
      }
    };

    fetchAllQuestions();
  }, [dispatch]);

  useEffect(() => {
    if (homeClicked && chatContainerRef.current) {
      const container = chatContainerRef.current;
      setTimeout(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth',
        });
      }, 500);
    }
  }, [homeClicked]);

  useEffect(() => {
    if (feedbackClicked && chatContainerRef.current) {
      const container = chatContainerRef.current;
      setTimeout(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth',
        });
      }, 500 );
    }
  }, [feedbackClicked]);

  useEffect(() => {
    if (chatContainerRef.current) {
      const container = chatContainerRef.current;
      setTimeout(
        () =>
          container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth',
          }),
        500
      );
    }
  }, [
    chatHistory,
    chatHistory.map((item) => item.loading).join(','),
    chatHistory.map((item) => item.is_greet).join(','),
    chatHistory.map((item) => item.is_able).join(','),
    chatHistory.map((item) => item.is_freq).join(','),
  ]);

  useEffect(() => {
    if (!sentValue || !sent) return;

    dispatch(clearSent());

    const newChatItem: ChatItem = {
      query: sentValue,
      response: [],
      loading: true,
      flag: false,
      seniorMode: -1,
      is_greet: false,
      is_able: false,
      is_freq: false,
      is_smalltalk: false,
      needs_profile: false,
      missing_fields: [],
    };

    newChatItemRef.current = newChatItem;
    setChatHistory((prevHistory) => [...prevHistory, newChatItem]);
    dispatch(setIsLoading(true));

    const fetchResponse = async () => {
      try {
        const language = isKorean ? 'KO' : 'EN';

        // FAQ 직접 클릭: ID로 바로 조회 (classify/RAG 건너뜀)
        if (directFaqId !== null) {
          const data = await getFaqById(directFaqId);
          const faqs = data.faqs ?? [];
          setChatHistory((prevHistory) =>
            prevHistory.map((item) =>
              item.query === sentValue
                ? { ...item, response: faqs, loading: false }
                : item
            )
          );
          dispatch(setIsLoading(false));
          return;
        }

        const serverResponse = await sendQuestion(sentValue, language);
        if (serverResponse && serverResponse.id >= 0) {
          dispatch(setId(serverResponse.id));
        }

        if (serverResponse) {
          if (serverResponse.needs_profile) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, loading: false, needs_profile: true, missing_fields: serverResponse.missing_fields ?? [] }
                  : item
              )
            );
          } else if (serverResponse.is_greet) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, loading: false, is_greet: true }
                  : item
              )
            );
          } else if (serverResponse.is_able) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, loading: false, is_able: true }
                  : item
              )
            );
          } else if (serverResponse.is_freq) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, loading: false, is_freq: true }
                  : item
              )
            );
          } else if (serverResponse.is_smalltalk && Array.isArray(serverResponse.faqs)) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, response: serverResponse.faqs, loading: false, is_smalltalk: true }
                  : item
              )
            );
          } else if (Array.isArray(serverResponse.faqs)) {
            setChatHistory((prevHistory) =>
              prevHistory.map((item) =>
                item.query === sentValue
                  ? { ...item, response: serverResponse.faqs, loading: false }
                  : item
              )
            );
          } else {
            console.error('Invalid response structure:', serverResponse);
            setError('Invalid response structure');
          }
          dispatch(setIsLoading(false));
        }
      } catch (err) {
        console.error('Error while fetching response:', err);
        setError(err as string);
        dispatch(setIsLoading(false));
        setChatHistory((prevHistory) =>
          prevHistory.map((item) =>
            item.query === sentValue ? { ...item, loading: false } : item
          )
        );
      }
    };

    fetchResponse();
  }, [sentValue, sent]);

  useEffect(() => {
    if (seniorFaqId !== null && seniorFaqId !== undefined) {
      const newChatItem: ChatItem = {
        query: '',
        response: [],
        loading: false,
        flag: false,
        seniorMode: -1,
        is_greet: false,
        is_able: true,
        is_freq: false,
        is_smalltalk: false,
        needs_profile: false,
        missing_fields: [],
        initialSeniorFaqId: seniorFaqId,
      };
      newChatItemRef.current = newChatItem;
      setChatHistory((prevHistory) => [...prevHistory, newChatItem]);
    }
  }, [seniorFaqId]);

  useEffect(() => {
    if (homeClicked) {
      const newChatItem: ChatItem = {
        query: '',
        response: [],
        loading: false,
        flag: true,
        seniorMode: -1,
        is_greet: false,
        is_able: false,
        is_freq: false,
        is_smalltalk: false,
        needs_profile: false,
        missing_fields: [],
      };

      setChatHistory((prevHistory) => [...prevHistory, newChatItem]);
      dispatch(resetHomeClicked());
    }
  }, [homeClicked, dispatch]);

  return (
    <div
      ref={chatContainerRef}
      className="flex flex-col h-full overflow-y-auto px-4 py-6 md:px-[20px] md:py-[30px] pb-[80px] md:pb-[100px]"
    >
      <HelloHobit />
      {chatHistory.map((chatItem, index) => (
        <div key={index}>
          {chatItem.seniorMode >= 0 ? (
            <div className="mt-6 md:mt-[40px] empty:hidden">
              <SeniorResponse 
                seniorFaqId={chatItem.seniorMode} 
                onBack={removeLastChatItem}
              />
            </div>
          ) : chatItem.flag ? (
            <div className="mt-6 md:mt-[40px]">
              <HelloHobit />
            </div>
          ) : (
            <>
              <div className={!chatItem.query ? 'invisible' : ''}>
                <Query text={chatItem.query} />
              </div>
              {chatItem.needs_profile ? (
                <ProfileInput
                  missingFields={chatItem.missing_fields}
                  onSaved={() => {
                    // 프로필 저장 후 같은 쿼리 재시도: loading 상태로 리셋 후 fetchResponse 재호출
                    const retryQuery = chatItem.query;
                    const retryLanguage = isKorean ? 'KO' : 'EN';
                    setChatHistory((prev) =>
                      prev.map((item) =>
                        item.query === retryQuery
                          ? { ...item, loading: true, needs_profile: false, missing_fields: [] }
                          : item
                      )
                    );
                    sendQuestion(retryQuery, retryLanguage).then((serverResponse) => {
                      if (!serverResponse) return;
                      if (serverResponse.id >= 0) dispatch(setId(serverResponse.id));
                      if (serverResponse.needs_profile) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false, needs_profile: true, missing_fields: serverResponse.missing_fields ?? [] } : item));
                      } else if (serverResponse.is_greet) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false, is_greet: true } : item));
                      } else if (serverResponse.is_able) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false, is_able: true } : item));
                      } else if (serverResponse.is_freq) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false, is_freq: true } : item));
                      } else if (serverResponse.is_smalltalk && Array.isArray(serverResponse.faqs)) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, response: serverResponse.faqs, loading: false, is_smalltalk: true } : item));
                      } else if (Array.isArray(serverResponse.faqs)) {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, response: serverResponse.faqs, loading: false } : item));
                      } else {
                        setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false } : item));
                      }
                    }).catch((err) => {
                      console.error('재시도 중 오류:', err);
                      setChatHistory((prev) => prev.map((item) => item.query === retryQuery ? { ...item, loading: false } : item));
                    });
                  }}
                />
              ) : chatItem.is_able ? (
                <AllCategoriesResponse initialSeniorFaqId={chatItem.initialSeniorFaqId} />
              ) : chatItem.is_greet ? (
                <GreetResponse />
              ) : chatItem.is_freq ? (
                <FAQResponse />
              ) : (
                <GeneralResponse
                  faqs={chatItem.response}
                  loading={chatItem.loading}
                />
              )}
            </>
          )}
        </div>
      ))}
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}
    </div>
  );
};

export default Chatting;
