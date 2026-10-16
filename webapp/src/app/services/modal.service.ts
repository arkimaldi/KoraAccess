// Copiat de KapriCloudWebManager (src/app/services/modal.service.ts) sense canvis.
// Si es modifica allà, convé portar-hi els canvis.

import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';

export type ModalStateType = {
    currentModalStack: string[],
    previousModalStack: string[],
    data?: any
};

export type ParsedModalStateType = {
    isVisible: boolean,
    isOnOpen: boolean,
    isOnClose: boolean
}

@Injectable({
    providedIn: 'root'
})
export class ModalService {
    private modalState = new BehaviorSubject<ModalStateType>({ currentModalStack: [], previousModalStack: []});
    private resultSubjects: { [key: string]: Subject<any> | null } = {};

    openModal(modalName: string, data?: any): Observable<any> {
        if (this.modalState.value.currentModalStack.includes(modalName)) {
            console.log('ModalService ERROR - openModal is opening a modal that is already in modalStack');
        };
        this.modalState.value.previousModalStack = [ ...this.modalState.value.currentModalStack];
        this.modalState.value.currentModalStack.push(modalName);
        this.resultSubjects[modalName] = new Subject<any>();
        this.modalState.next({ currentModalStack: this.modalState.value.currentModalStack, previousModalStack: this.modalState.value.previousModalStack, data: data });
        return this.resultSubjects[modalName]!.asObservable();
    }

    closeModal(result?: any) {
        if (this.modalState.value.currentModalStack.length === 0) {
            console.log('ModalService ERROR - closeModal called without any previously opened modal');
            return;
        };
        this.modalState.value.previousModalStack = [ ...this.modalState.value.currentModalStack];
        const closingModalName = this.modalState.value.currentModalStack.pop();
        this.modalState.next({ currentModalStack: this.modalState.value.currentModalStack, previousModalStack: this.modalState.value.previousModalStack });
        if (closingModalName && this.resultSubjects[closingModalName]) {
            this.resultSubjects[closingModalName]!.next(result);
            this.resultSubjects[closingModalName]!.complete();
            this.resultSubjects[closingModalName] = null;
        }
    }

    getModalState(): Observable<ModalStateType> {
        return this.modalState.asObservable();
    }

    private getPhase(modalName: string, modalStack: string[]): 'closed' | 'background' | 'foreground' {
        if (modalStack.length > 0 && modalStack[modalStack.length -1] === modalName) return 'foreground';
        if (modalStack.includes(modalName)) return 'background';
        return 'closed'
    }

    parseModalState(modalName: string, modalState: ModalStateType): ParsedModalStateType {
        const currentPhase = this.getPhase(modalName, modalState.currentModalStack);
        const previousPhase = this.getPhase(modalName, modalState.previousModalStack);
        return {
            isVisible: (['foreground', 'background'].includes(currentPhase)),
            isOnOpen: (currentPhase === 'foreground' && previousPhase === 'closed'),
            isOnClose: (currentPhase === 'closed' && previousPhase === 'foreground')
        }
    }
}

/*
Com usar aquest servei.

COMPONENT QUE OBRE MODALS
El component que obre modals cridarà al mètode openModal i se subscriurà a l'observable retornat 
per capturar la resposta del modal. 

Aquesta resposta serà undefined, si el modal tanca sense passar resultats, és a dir executant this.closeModal();
Això tindira el significat que el modal s'ha tancat amb el botó "cancel".

Si sortim del modal per botó "process", llavors el modal es tanca executant this.closeModal(myResults ?? null);
La idea és passar un null per indicar que hi ha resultats sense dades i passar un valor si hi ha resultats.
L'expressió ?? null evita passar un undefined, fet que podria confondre's amb "cancel".

Implementació:

al .ts:

1) importació
import { ModalService } from '../../services/modal.service';

2) injecció
    private modalService: ModalService,

3) obertura

    this.modalService.openModal('app-modal-template-select', {group_id: this.$group()?.group_id || null})
        .pipe(takeUntil(this.destroy$))
        .subscribe(result => {
            if (result !== undefined) {                 // quan result es undefined indica que el modal s'ha cancel·lat
                this.openModalConfigCreate(result);        // result és null si no s'ha escollit cap template
            }
    });

    on:

    openModalConfigCreate(selectedConfig: ConfigBaseListElement): void {
        this.modalService.openModal('app-modal-config-create', {group_id: this.$group()?.group_id || null, selectedConfig: selectedConfig});
    }

    o:

    this.modalService.openModal('app-modal-change-password', {user_id: this.$token().lgus?.user_id || null})
        .pipe(takeUntil(this.destroy$))
        .subscribe(result => {
            if (result !== undefined) { // quan result es undefined indica que el modal s'ha cancel·lat
                this.onModalClose();
            }
        });

a l'html:

1) cridar el modal

<app-modal-template-select></app-modal-template-select>


COMPONENT MODAL

Implementació:

al .ts:

1) importació
import { OnInit, .... } from '@angular/core';
import { ModalService, ParsedModalStateType } from '../../../services/modal.service';

2) implementació de ngOnInit
    a la classe afegim: implements OnInit

3) definició de propietats modals

    static readonly modalMe = 'app-modal-template-select';
    modalIsVisible: boolean = false;

4) injecció
    private modalService: ModalService,

5) init i destroy

    ngOnInit() {
        this.modalService.getModalState()
        .pipe(takeUntil(this.destroy$))
        .subscribe(modalState => {
            const parsedModalState: ParsedModalStateType = this.modalService.parseModalState(myClassComponent.modalMe, modalState);
            this.modalIsVisible = parsedModalState.isVisible;
            if (parsedModalState.isOnOpen) {   
                this.onOpen(modalState.data);
            } else if (parsedModalState.isOnClose) {
                this.onClose();
            }
        });
    }

    ngOnDestroy() {
        this.destroy$.next();
        this.destroy$.complete();
    }

    onOpen(modalData: any): void {
        this.parseModalData(modalData);
        this.initProperties();
        this.clearMessageError();
        ...
        this.altresCoses();
    }

    onClose(): void {

    }

    parseModalData(modalData: any): void {
        this.myProperty = modalData.myPropertyValue;
    }

    initProperties() {
        this.myOtherProperty = '';
    }

6) tancament:

    closeModalCancelled() {
        this.modalService.closeModal();
    }

    closeModalWithResult() {
        this.modalService.closeModal({myResult: this.myResult} ?? null);
    }

a l'html:

1) condicionar l'obertura:
    <div class="modal-overlay" *ngIf="modalIsVisible">

NOTA:

Es possible obrir un modal des d'un modal previa crida del closeModal.
No és possible la reobertura del mateix modal.
*/