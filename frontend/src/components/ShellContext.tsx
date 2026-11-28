"use client";

import { createContext, useContext } from "react";
import type { ContractOut } from "../lib/api";

// 지금 화면의 계약서(이름·상태). AppShell이 `GET /contracts/{id}`를 한 번 불러 둔다.
type ContractState = { contract: ContractOut | null; reload: () => void };
export const ContractContext = createContext<ContractState>({ contract: null, reload: () => {} });
export const useContract = () => useContext(ContractContext);

// 사이드바의 내 계약서 목록(`GET /contracts`). 화면이 계약서를 올리거나 지운 뒤 reloadContracts()로 맞춘다.
type ContractsState = { contracts: ContractOut[] | null; reloadContracts: () => Promise<void> };
export const ContractsContext = createContext<ContractsState>({ contracts: null, reloadContracts: async () => {} });
export const useContracts = () => useContext(ContractsContext);
