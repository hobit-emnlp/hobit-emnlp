// inputSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface InputState {
	isEmpty: boolean;
	sentValue: string;
	liveValue: string;
	sent: boolean;
	directFaqId: number | null;  // FAQ 직접 클릭 시 ID
	isLoading: boolean;

	// out of ctx
	id: number;
}

const initialState: InputState = {
	isEmpty: true,
	sentValue: '',
	liveValue: '',
	sent: false,
	directFaqId: null,
	isLoading: false,

	id: -1,
};

const inputSlice = createSlice({
	name: 'input',
	initialState,
	reducers: {
		setIsEmpty: (state, action: PayloadAction<boolean>) => {
			state.isEmpty = action.payload;
		},
		sendInputValue: (state, action: PayloadAction<string>) => {
			state.sentValue = action.payload;
			state.liveValue = '';
			state.isEmpty = true;
			state.sent = true;
			state.directFaqId = null;
		},
		sendFaqById: (state, action: PayloadAction<{ id: number; query: string }>) => {
			state.sentValue = action.payload.query;
			state.liveValue = '';
			state.isEmpty = true;
			state.sent = true;
			state.directFaqId = action.payload.id;
		},
		clearSent: (state) => {
			state.sent = false;
			state.directFaqId = null;
		},
		clearSentValue: (state) => {
			state.sentValue = '';
		},
		updateLiveValue: (state, action: PayloadAction<string>) => {
			state.liveValue = action.payload;
			state.isEmpty = action.payload === '';
		},

		setIsLoading: (state, action: PayloadAction<boolean>) => {
			state.isLoading = action.payload;
		},

		// ooc
		setId: (state, action: PayloadAction<number>) => {
			state.id = action.payload;
		},
	},
});

export const {
	setIsEmpty,
	sendInputValue,
	sendFaqById,
	clearSentValue,
	clearSent,
	updateLiveValue,
	setIsLoading,
	setId,
} = inputSlice.actions;
export const inputReducer = inputSlice.reducer;
