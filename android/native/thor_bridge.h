#pragma once
class GadgetClass;
extern bool Thor_ExplicitAction;
void Thor_Pump();
void Thor_Gadgets(GadgetClass* first);
void Thor_Viewport(int width, int height, int& x, int& y, int& w, int& h);
void Thor_Mission(bool active);
